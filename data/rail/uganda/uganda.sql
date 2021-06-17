-- pgRouting requires the source and target nodes to be integer ids.
-- Need to amend node and edge ids to integer

-- add souce and target columns
ALTER TABLE uganda_osm_edges
		ADD COLUMN length float4,
    ADD COLUMN source integer, 
		ADD COLUMN target integer,
		ADD COLUMN oid integer,
		ADD COLUMN line text,
		ADD COLUMN gauge text,
		ADD COLUMN status text, -- open, abandoned, disused, rehabilitation, construction, proposed
		ADD COLUMN mode text, -- passenger, freight or mixed.
		ADD COLUMN structure text, -- bridges etc
		ADD COLUMN speed_freight integer,
		ADD COLUMN speed_passenger integer,
		ADD COLUMN comment text;
		
-- calculate edge lengths (need to transform to projected - use EPSG:21036)
UPDATE uganda_osm_edges set length = round(st_length(st_transform(geom, 21036))::numeric,2);

-- assume mixed mode unless amended
UPDATE uganda_osm_edges set mode = 'mixed';
		
-- copy integer ids component
-- uganda ids start 4440000
UPDATE uganda_osm_edges set source = 4440000 + reverse(split_part(reverse(from_id), '_', 1))::int4;
UPDATE uganda_osm_edges set target = 4440000 + reverse(split_part(reverse(to_id), '_', 1))::int4;
UPDATE uganda_osm_edges set oid = 4440000 + reverse(split_part(reverse(id), '_', 1))::int4;

-- make primary key
ALTER TABLE uganda_osm_edges DROP CONSTRAINT uganda_osm_edges_pkey;
ALTER TABLE uganda_osm_edges ADD PRIMARY KEY (oid);

-- add oid column to nodes
ALTER TABLE uganda_osm_nodes ADD COLUMN oid int4;
UPDATE uganda_osm_nodes set oid = 4440000 + reverse(split_part(reverse(id), '_', 1))::int4;

-- make primary key
ALTER TABLE uganda_osm_nodes DROP CONSTRAINT uganda_osm_nodes_pkey;
ALTER TABLE uganda_osm_nodes ADD PRIMARY KEY (oid);

-- add columns to nodes
alter table uganda_osm_nodes
ADD COLUMN gauge text,
ADD COLUMN facility text; -- dry_port, port, gauge_interchange, manufacturer


-- set additional node for stations
update uganda_osm_nodes
set name = 'Kampala',
railway = 'station'
where oid = 4441152;

update uganda_osm_nodes
set name = 'Namanve',
railway = 'station'
where oid = 4440864;

-- facilities

-- manufacturer
update uganda_osm_nodes
set facility = 'manufacturer',
name = 'Tororo Cement',
railway = 'stop'
where oid = 4440918;

-- port
update uganda_osm_nodes
set facility = 'port',
name = 'Port Bell',
railway = 'stop'
where oid = 4440870;

update uganda_osm_nodes
set facility = 'port',
name = 'Jinja Pier',
railway = 'stop'
where oid = 4441014;

-- dry port (Gulu Station)
update uganda_osm_nodes
set facility = 'dry_port'
where oid in (4440609);


-- Update status - copy over from railway key if 'abandoned', 'disused'

UPDATE uganda_osm_edges
 SET status =
 CASE WHEN railway in ('abandoned', 'disused') THEN railway
 WHEN railway in ('rail', 'narrow_gauge') THEN 'open'
 else 'unknown'
 end;
 
 -- Update structure
 
 update uganda_osm_edges
 set structure = 
 CASE WHEN bridge = 'yes' then 'bridge'
 WHEN bridge = 'viaduct' then 'viaduct'
 WHEN railway in ('platform', 'station') THEN railway
 end;
 
 
-- populate gauge column
-- incorrectly coded rail in OSM data. This will need to be set per route.

-- remove unused columns from edges
alter table uganda_osm_edges
drop column id,
drop column fid,
drop column osm_id,
drop column bridge,
drop column railway,
drop column name,
drop column is_current,
drop column from_id,
drop column to_id;

-- remove unused columns from nodes
alter table uganda_osm_nodes
drop column id,
drop column fid,
drop column osm_id,
drop column is_current;

-- update where name null and station/halt/stop
-- otherwise unnamed

update uganda_osm_nodes
set name =
(case when oid = 4440264 then 'Namaganda'
when oid = 4440533 then 'Lakwatomer'
when oid = 4440575 then 'Awat Lela'
else 'unnamed'
end)
where name is null and railway in ('station', 'stop', 'halt');


-- create new station nodes
-- this is required as there can be several edges running through stations but the station node
-- is located on an edge that isn't used for the route.
-- Jinja 4440051 to 4440249

DO $$ DECLARE
-- create new station nodes
-- note: must not be a node coincident with the closest point (reassign that node as a station instead)
 nodes INT ARRAY DEFAULT ARRAY [4440051];
 edges INT ARRAY DEFAULT ARRAY [4440249];
-- nodes INT ARRAY DEFAULT ARRAY [];
-- edges INT ARRAY DEFAULT ARRAY [];
node INT;
edge INT;
idx INT;
closest_point GEOMETRY;
newline GEOMETRY;
orsource int;
ortarget int;
BEGIN
		for node, edge in select unnest(nodes), unnest(edges)
		LOOP

-- want a new station node on the nearest point on the required edge and split the edge for routing
-- find index of nearest segment to the point in the line. We want to insert a new point (vertex) into the line so we can split it at the station
-- use function ST_LineLocateN
SELECT ST_LineLocateN(e.geom, n.geom) from uganda_osm_nodes n, uganda_osm_edges e where n.oid = node and e.oid = edge
into idx;
-- closest point
select ST_ClosestPoint(e.geom, n.geom) from uganda_osm_nodes n, uganda_osm_edges e where n.oid = node and e.oid = edge into closest_point;
-- new line geometry with added point
select ST_AddPoint(e.geom, closest_point, idx) from uganda_osm_edges e where e.oid = edge into newline;
-- original source and target
select target from uganda_osm_edges where oid = edge into ortarget;
select source from uganda_osm_edges where oid = edge into orsource;

raise notice 'counter: %', node || ' ' || edge || ' ' || idx || ' ' || orsource || ' ' || ortarget ;	

-- create new node for station
INSERT INTO uganda_osm_nodes (name, geom, railway, oid)
SELECT name, closest_point, railway, oid + 10000
FROM uganda_osm_nodes
WHERE oid = node;
 
insert into uganda_osm_edges 
with tmp as ( select a.*, ( st_dump ( st_split ( newline, closest_point ) ) ).geom as geom2 from uganda_osm_edges a where oid = edge ),
	tmp2 as ( select geom2 as geom, length, ( oid :: text || row_number ( ) over ( ) ) :: int as oid, line, gauge, status, mode, structure, speed_freight, speed_passenger, comment, st_startpoint ( geom2 ), st_endpoint ( geom2 ) from tmp ) select
	a.geom,
	round( st_length ( st_transform ( a.geom, 21036 ) ) :: numeric, 2 ) as length,
	b.oid as source,
	c.oid as target,
	a.oid,
	line,
	a.gauge,
	status,
	mode,
	structure,
	speed_freight,
	speed_passenger,
	comment 
	from
		tmp2 a JOIN uganda_osm_nodes b ON st_dwithin( b.geom, a.st_startpoint, .000000001 )
		-- need st_dwithin rather than st_intersects 
		JOIN uganda_osm_nodes c ON st_dwithin ( c.geom, a.st_endpoint, .00000000001 )
		-- there can be additional nodes than the original target and source nodes at the original line end /start points
		-- so have to limit results 
		where b.oid in (ortarget, orsource) or c.oid in (ortarget,orsource)
	;
	
	-- delete the original edge
	delete 
	from
	uganda_osm_edges 
	where
	oid = edge;
	
	-- delete original station node
	-- don't think will do that, will just select the station nodes that intersect the required routes.
	-- delete 
	-- from
	-- uganda_osm_nodes 
	-- where
	-- oid = node;
	

END LOOP;
END $$;


-- psql code to fix routing issue. Splits edge at node.

-- allow routing through Jinja
-- split 4440480 at 4440924

-- allow routing out of Tororo to Gulu
-- split 4440184 at 4441220
-- split 4441121 at 4441221

-- allow routing north of Lira
-- split 4440265 at 4440935

-- Busoga loop (section to Busembatia)
-- split 4440417 at 4440968

-- Kampala to Kasese
-- split 4440825 at 4441158
-- split 4440857 at 4441159
-- split 4440987 at 4441107

DO $$ DECLARE
 edges INT ARRAY DEFAULT ARRAY [4440480, 4440184, 4441121, 4440265, 4440417, 4440825, 4440857, 4440987];
 nodes INT ARRAY DEFAULT ARRAY [4440924, 4441220, 4441221, 4440935, 4440968, 4441158, 4441159, 4441107];
-- edges INT ARRAY DEFAULT ARRAY [4440987];
-- nodes INT ARRAY DEFAULT ARRAY [4441107];
edge INT;
node INT;
BEGIN
		for edge, node in select unnest(edges), unnest(nodes)
		LOOP
		raise notice'counter: %', edge || ' ' || node;
	insert into uganda_osm_edges with tmp as (select a.*, (st_dump(st_split(a.geom, b.geom))).geom as geom2 from uganda_osm_edges a, uganda_osm_nodes b where a.oid = edge and b.oid = node),
	tmp2 as (select geom2 as geom, length, ( oid :: text || row_number ( ) over ( ) ) :: int as oid, line, gauge, status, mode, structure, speed_freight, speed_passenger, comment, st_startpoint ( geom2 ), st_endpoint ( geom2 ) from tmp ) select 
	a.geom,
	round( st_length ( st_transform ( a.geom, 21036 ) ) :: numeric, 2 ) as length,
	b.oid as source,
	c.oid as target,
	a.oid,
	a.line,
	a.gauge,
	a.status,
	a.mode,
	a.structure,
	a.speed_freight,
	a.speed_passenger,
	comment 
	from
		tmp2
		a JOIN uganda_osm_nodes b ON st_intersects ( b.geom, a.st_startpoint )
		JOIN uganda_osm_nodes c ON st_intersects ( c.geom, a.st_endpoint );
	delete 
	from
		uganda_osm_edges 
	where
		oid = edge;
END LOOP;
END $$;

-- routes

-- Kamapala - Jinja
with tmp as(
SELECT X.* FROM pgr_dijkstra(
                'SELECT oid as id, source, target, length AS cost FROM uganda_osm_edges',
                4441152,
		4450051,
		false
		) AS X
		ORDER BY seq)
update uganda_osm_edges
set line = 'Kampala - Malaba',
gauge = '1000',
status = 'open',
mode = 'freight'
where oid in (select edge from tmp);

-- Jinja - Malaba
with tmp as(
SELECT X.* FROM pgr_dijkstra(
                'SELECT oid as id, source, target, length AS cost FROM uganda_osm_edges',
                4450051,
		4440911,
		false
		) AS X
		ORDER BY seq)
update uganda_osm_edges
set line = 'Kampala - Malaba',
gauge = '1000',
status = 'open',
mode = 'freight'
where oid in (select edge from tmp);

-- commuter train Namanve - Kampala
with tmp as(
SELECT X.* FROM pgr_dijkstra(
                'SELECT oid as id, source, target, length AS cost FROM uganda_osm_edges',
                4441152,
		4440864,
		false
		) AS X
		ORDER BY seq)
update uganda_osm_edges
set line = 'Kampala - Malaba',
gauge = '1000',
status = 'open',
mode = 'mixed'
where oid in (select edge from tmp);

-- Kampala to Port Bell
with tmp as(
SELECT X.* FROM pgr_dijkstra(
                'SELECT oid as id, source, target, length AS cost FROM uganda_osm_edges',
                4441214,
		4440870,
		false
		) AS X
		ORDER BY seq)
update uganda_osm_edges
set line = 'Kampala - Port Bell',
gauge = '1000',
status = 'open',
mode = 'freight'
where oid in (select edge from tmp);

-- insert line for simplified routing from Jinja to Jinja Pier
with tmp as
(
select st_makeline(a.geom, b.geom) as line from uganda_osm_nodes a, uganda_osm_nodes b where a.oid = 4441013 and b.oid = 4450051)
insert into uganda_osm_edges select 
a.line,
round( st_length ( st_transform ( a.line, 21036 ) ) :: numeric, 2 ) as length,
4441013,
4450051,
4460001
from tmp as a;

-- Jinja Pier
with tmp as(
SELECT X.* FROM pgr_dijkstra(
                'SELECT oid as id, source, target, length AS cost FROM uganda_osm_edges',
                4450051,
		4441014,
		false
		) AS X
		ORDER BY seq)
update uganda_osm_edges
set line = 'Jinja - Jinja Pier',
gauge = '1000',
status = 'open',
mode = 'freight'
where oid in (select edge from tmp);

-- insert line gap on Tororo - Gulu
with tmp as
(
select st_makeline(a.geom, b.geom) as line from uganda_osm_nodes a, uganda_osm_nodes b where a.oid = 4440944 and b.oid = 4440946)
insert into uganda_osm_edges select 
a.line,
round( st_length ( st_transform ( a.line, 21036 ) ) :: numeric, 2 ) as length,
4440944,
4440946,
4460002
from tmp as a;

-- Tororo - Gulu
with tmp as(
SELECT X.* FROM pgr_dijkstra(
                'SELECT oid as id, source, target, length AS cost FROM uganda_osm_edges',
                4441221,
		4440609,
		false
		) AS X
		ORDER BY seq)
update uganda_osm_edges
set line = 'Tororo - Gulu',
gauge = '1000',
status = 'rehabilitation',
mode = 'freight',
comment = 'EU part funded rehabilitation project, completion expected 2023'
where oid in (select edge from tmp);

-- Gulu to Pakwach
with tmp as(
SELECT X.* FROM pgr_dijkstra(
                'SELECT oid as id, source, target, length AS cost FROM uganda_osm_edges',
                4440609,
		4440941,
		false
		) AS X
		ORDER BY seq)
update uganda_osm_edges
set line = 'Gulu - Pakwach',
gauge = '1000',
status = 'disused',
mode = 'freight'
where oid in (select edge from tmp);

-- abandoned Kampala to Kasese line
-- join two nodes where no connecting line (for routing)
with tmp as
(
select st_makeline(a.geom, b.geom) as line from uganda_osm_nodes a, uganda_osm_nodes b where a.oid = 4440894 and b.oid = 4440896)
insert into uganda_osm_edges select 
a.line,
round( st_length ( st_transform ( a.line, 21036 ) ) :: numeric, 2 ) as length,
4440894,
4440896,
4460003
from tmp as a;

-- Nalukolongo - Kasese
with tmp as(
SELECT X.* FROM pgr_dijkstra(
                'SELECT oid as id, source, target, length AS cost FROM uganda_osm_edges',
                4440523,
		4440341,
		false
		) AS X
		ORDER BY seq)
update uganda_osm_edges
set line = 'Kampala - Kasese',
gauge = '1000',
status = 'abandoned'
where oid in (select edge from tmp);

with tmp as(
SELECT X.* FROM pgr_dijkstra(
                'SELECT oid as id, source, target, length AS cost FROM uganda_osm_edges',
                4440004,
		4441107,
		false
		) AS X
		ORDER BY seq)
update uganda_osm_edges
set line = NULL,
gauge = NULL,
status = 'open'
where oid in (select edge from tmp);


-- Kampala - Nalukolongo section still in use (freight)
with tmp as(
SELECT X.* FROM pgr_dijkstra(
                'SELECT oid as id, source, target, length AS cost FROM uganda_osm_edges',
                4441152,
		4440523,
		false
		) AS X
		ORDER BY seq)
update uganda_osm_edges
set line = 'Kampala - Kasese',
gauge = '1000',
status = 'open'
where oid in (select edge from tmp);

-- insert line to simplify routing onto Busoga Railway
with tmp as
(
select st_makeline(a.geom, b.geom) as line from uganda_osm_nodes a, uganda_osm_nodes b where a.oid = 4440193 and b.oid = 4450051)
insert into uganda_osm_edges select 
a.line,
round( st_length ( st_transform ( a.line, 21036 ) ) :: numeric, 2 ) as length,
4440193,
4450051,
4460004
from tmp as a;

-- Busoga Railway
-- remove edge on main Jinja to Tororo line to ensure correct route
with tmp as(
SELECT X.* FROM pgr_dijkstra(
                'SELECT oid as id, source, target, length AS cost FROM (select * from uganda_osm_edges where oid != 4440248) as a',
                4450051,
		4440950,
		false
		) AS X
		ORDER BY seq)
update uganda_osm_edges
set line = 'Busoga Loop',
gauge = '1000',
status = 'disused',
comment = 'Vandalised (substantial removal of tracks) and is out of use'
where oid in (select edge from tmp);

-- Busoga Loop into Busembatia
with tmp as(
SELECT X.* FROM pgr_dijkstra(
                'SELECT oid as id, source, target, length AS cost FROM uganda_osm_edges',
                4440968,
		4440969,
		false
		) AS X
		ORDER BY seq)
update uganda_osm_edges
set line = 'Busoga Loop',
gauge = '1000',
status = 'disused',
comment = 'Vandalised (substantial removal of tracks) and is out of use'
where oid in (select edge from tmp);

-- Tororo Cement line
-- simplify routing - add line to join 917 to 69
with tmp as
(
select st_makeline(a.geom, b.geom) as line from uganda_osm_nodes a, uganda_osm_nodes b where a.oid = 4440917 and b.oid = 4440069)
insert into uganda_osm_edges select 
a.line,
round( st_length ( st_transform ( a.line, 21036 ) ) :: numeric, 2 ) as length,
4440917,
4440069,
4460005
from tmp as a;

with tmp as(
SELECT X.* FROM pgr_dijkstra(
                'SELECT oid as id, source, target, length AS cost FROM uganda_osm_edges',
                4440069,
		4440918,
		false
		) AS X
		ORDER BY seq)
update uganda_osm_edges
set line = 'Tororo Cement',
gauge = '1000',
status = 'open',
mode = 'freight'
where oid in (select edge from tmp);


-- create spatial indexes
CREATE INDEX uganda_osm_edges_geom_idx
  ON uganda_osm_edges
  USING GIST (geom);

CREATE INDEX uganda_osm_nodes_geom_idx
  ON uganda_osm_nodes
  USING GIST (geom);


-- update station gauge on stations

update uganda_osm_nodes
set gauge = '1000'
where st_intersects(geom, (select st_collect(geom) from uganda_osm_edges where gauge = '1000'))
and railway in ('station', 'halt', 'stop');


		
-- test routing		
		SELECT X.*, a.line, a.status, b.railway, b.name FROM pgr_dijkstra(
                'SELECT oid as id, source, target, length AS cost FROM (select * from uganda_osm_edges where oid != 248) as a',
                4450051,
4440950,
		false
		) AS X left join
		uganda_osm_edges as a on a.oid = X.edge left join
		uganda_osm_nodes as b on b.oid = X.node
		ORDER BY seq;
			
	-- functions		
	-- from: https://gis.stackexchange.com/a/370562
	-- a SQL function to compute the segment index of the LineString segment closest to a given point
	-- Example:
	-- 
	-- SELECT ST_LineLocateN( 'LINESTRING (0 0, 10 10, 20 20, 30 30)'::geometry, 
	--   'POINT(15 15.1)'::geometry);
	-- ==> 2
-- 		CREATE OR REPLACE FUNCTION ST_LineLocateN( line geometry, pt geometry )
-- RETURNS integer
-- AS $$
--     SELECT i FROM (
--     SELECT i, ST_Distance(
--         ST_MakeLine( ST_PointN( line, s.i ), ST_PointN( line, s.i+1 ) ),
--         pt) AS dist
--       FROM generate_series(1, ST_NumPoints( line )-1) AS s(i)
--       ORDER BY dist
--     ) AS t LIMIT 1;
-- $$
-- LANGUAGE sql STABLE STRICT;
-- pgRouting requires the source and target nodes to be integer ids.
-- Need to amend node and edge ids to integer

-- add souce and target columns
ALTER TABLE tanzania_osm_edges
		ADD COLUMN length float4,
    ADD COLUMN source integer, 
		ADD COLUMN target integer,
		ADD COLUMN oid integer,
		ADD COLUMN line text,
		ADD COLUMN gauge text,
		ADD COLUMN status text,
		ADD COLUMN mode text, -- passenger, freight or mixed.
		ADD COLUMN structure text; -- bridges etc
		
-- calculate edge lengths (need to transform to projected - use EPSG:21036)
UPDATE tanzania_osm_edges set length = round(st_length(st_transform(geom, 21036))::numeric,2);

-- assume mixed mode unless amended
UPDATE tanzania_osm_edges set mode = 'mixed';
		
-- copy integer ids component
UPDATE tanzania_osm_edges set source = reverse(split_part(reverse(from_id), '_', 1))::int4;
UPDATE tanzania_osm_edges set target = reverse(split_part(reverse(to_id), '_', 1))::int4;
UPDATE tanzania_osm_edges set oid = reverse(split_part(reverse(id), '_', 1))::int4;

-- make primary key
ALTER TABLE tanzania_osm_edges DROP CONSTRAINT tanzania_osm_edges_pkey;
ALTER TABLE tanzania_osm_edges ADD PRIMARY KEY (oid);

-- add oid column to nodes
ALTER TABLE tanzania_osm_nodes ADD COLUMN oid int4;
UPDATE tanzania_osm_nodes set oid = reverse(split_part(reverse(id), '_', 1))::int4;

-- make primary key
ALTER TABLE tanzania_osm_nodes DROP CONSTRAINT tanzania_osm_nodes_pkey;
ALTER TABLE tanzania_osm_nodes ADD PRIMARY KEY (oid);

-- add gauge column to nodes
alter table tanzania_osm_nodes
add COLUMN gauge text;

-- metre-gauge lines into Dar es Salaam currently stop before central station.
-- This is presumably temporary due to construction work on SGR viaduct?
-- connect lines 3193 and 1738 to node 2786 (at beginning of line)
UPDATE tanzania_osm_edges
	SET geom = ST_AddPoint(geom, (select geom from tanzania_osm_nodes where oid = 2786), 0),
	source = 2786
   WHERE oid IN (3193, 1738);
-- update line length
UPDATE tanzania_osm_edges
	SET length = round(st_length(st_transform(geom, 32736 ))::numeric,2)
	WHERE oid IN (3193, 1738);

-- delete duplicate station nodes(on same gauge)
-- may just select those coincident with defined routes for export?

-- delete from tanzania_osm_nodes where oid in (1343, 92, 1, 1347, 1345, 1337, 1305)

-- update nodes values

-- set additional node for stations
update tanzania_osm_nodes
set name = '',
railway = 'station'
where oid = ;

-- incorrect name

update tanzania_osm_nodes
set name = ''
where oid = ;


-- Update status - copy over from railway key if 'abandoned', 'construction', 'dismantled', 'disused', 'preserved'

UPDATE tanzania_osm_edges
 SET status =
 CASE WHEN railway in ('abandoned', 'construction', 'dismantled', 'disused', 'preserved') THEN railway
 WHEN railway in ('rail', 'narrow_gauge') THEN 'open'
 else 'unknown'
 end;
 
 -- Update structure
 
 update tanzania_osm_edges
 set structure = 
 CASE WHEN bridge = 'yes' then 'bridge'
 WHEN bridge = 'viaduct' then 'viaduct'
 WHEN railway in ('level_crossing', 'platform', 'station', 'turntable') THEN railway
 end;
 
 
-- populate gauge column
-- incorrectly coded rail and narrow_gauge in OSM data. This will need to be set per route.


-- remove unused columns from edges
alter table tanzania_osm_edges
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
alter table tanzania_osm_nodes
drop column id,
drop column fid,
drop column osm_id,
drop column is_current;

-- update where name null and station/halt/stop

-- otherwise unnamed

update tanzania_osm_nodes
set name = 
(case when oid =  then ''
when oid =  then ''
else 'unnamed'
end)
where name is null and railway in ('station', 'stop', 'halt');

-- create new station nodes
-- this is required as there can be several edges running through stations but the station node
-- is located on an edge that isn't used for the route.

-- Tabora station node 326 to 2583
-- Manyoni station node 478 to 1871

DO $$ DECLARE
-- create new station nodes
-- note: must not be a node coincident with the closest point (reassign that node as a station instead)
-- nodes INT ARRAY DEFAULT ARRAY [326, 478];
-- edges INT ARRAY DEFAULT ARRAY [2583, 1871];
nodes INT ARRAY DEFAULT ARRAY [478];
edges INT ARRAY DEFAULT ARRAY [1871];
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
SELECT ST_LineLocateN(e.geom, n.geom) from tanzania_osm_nodes n, tanzania_osm_edges e where n.oid = node and e.oid = edge
into idx;
-- closest point
select ST_ClosestPoint(e.geom, n.geom) from tanzania_osm_nodes n, tanzania_osm_edges e where n.oid = node and e.oid = edge into closest_point;
-- new line geometry with added point
select ST_AddPoint(e.geom, closest_point, idx) from tanzania_osm_edges e where e.oid = edge into newline;
-- original source and target
select target from tanzania_osm_edges where oid = edge into ortarget;
select source from tanzania_osm_edges where oid = edge into orsource;

raise notice 'counter: %', node || ' ' || edge || ' ' || idx || ' ' || orsource || ' ' || ortarget ;	

-- create new node for station
INSERT INTO tanzania_osm_nodes (name, geom, railway, oid)
SELECT name, closest_point, railway, oid + 10000
FROM tanzania_osm_nodes
WHERE oid = node;
 
insert into tanzania_osm_edges 
with tmp as ( select a.*, ( st_dump ( st_split ( newline, closest_point ) ) ).geom as geom2 from tanzania_osm_edges a where oid = edge ),
	tmp2 as ( select geom2 as geom, length, ( oid :: text || row_number ( ) over ( ) * 10000 ) :: int as oid, line, gauge, status, mode, structure, st_startpoint ( geom2 ), st_endpoint ( geom2 ) from tmp ) select
	a.geom,
	round( st_length ( st_transform ( a.geom, 21036 ) ) :: numeric, 2 ) as length,
	b.oid as source,
	c.oid as target,
	a.oid,
	line,
	gauge,
	status,
	mode 
	from
		tmp2 a JOIN tanzania_osm_nodes b ON st_dwithin( b.geom, a.st_startpoint, .000000001 )
		-- need st_dwithin rather than st_intersects 
		JOIN tanzania_osm_nodes c ON st_dwithin ( c.geom, a.st_endpoint, .00000000001 )
		-- there can be additional nodes than the original target and source nodes at the original line end /start points
		-- so have to limit results 
		where b.oid in (ortarget, orsource) or c.oid in (ortarget,orsource)
	;
	
	-- delete the original edge
	delete 
	from
	tanzania_osm_edges 
	where
	oid = edge;
	
	-- delete original station node
	-- don't think will do that, will just select the station nodes that intersect the required routes.
	-- delete 
	-- from
	-- tanzania_osm_nodes 
	-- where
	-- oid = node;
	

END LOOP;
END $$;


-- psql code to fix routing issue. Splits edge at node.

-- allow routing into Mpanda station
-- split 2850 at 2601

-- allow routing from Manyoni to Singida
-- split 137 at 2901

-- allow routing out of Kilosa to Msolwa
-- split 3518 at 3287

-- allow routing out of Ruvu to the Link Line to Mruazi
-- split 850 at 2585

DO $$ DECLARE
-- edges INT ARRAY DEFAULT ARRAY [2850, 137,  3518, 850];
-- nodes INT ARRAY DEFAULT ARRAY [2601, 2901, 3287, 2585];
edges INT ARRAY DEFAULT ARRAY [850];
nodes INT ARRAY DEFAULT ARRAY [2585];
edge INT;
node INT;
BEGIN
		for edge, node in select unnest(edges), unnest(nodes)
		LOOP
		raise notice'counter: %', edge || ' ' || node;
	insert into tanzania_osm_edges with tmp as (select a.*, (st_dump(st_split(a.geom, b.geom))).geom as geom2 from tanzania_osm_edges a, tanzania_osm_nodes b where a.oid = edge and b.oid = node),
	tmp2 as (select geom2 as geom, length, ( oid :: text || row_number ( ) over ( ) * 10000 ) :: int as oid, line, gauge, status, mode, structure, st_startpoint ( geom2 ), st_endpoint ( geom2 ) from tmp ) select 
	a.geom,
	round( st_length ( st_transform ( a.geom, 21036 ) ) :: numeric, 2 ) as length,
	b.oid as source,
	c.oid as target,
	a.oid,
	a.line,
	a.gauge,
	a.status,
	a.mode,
	a.structure 
	from
		tmp2
		a JOIN tanzania_osm_nodes b ON st_intersects ( b.geom, a.st_startpoint )
		JOIN tanzania_osm_nodes c ON st_intersects ( c.geom, a.st_endpoint );
	delete 
	from
		tanzania_osm_edges 
	where
		oid = edge;
END LOOP;
END $$;

-- routes

-- Central Line to Kigoma passenger station
with tmp as(
SELECT X.* FROM pgr_dijkstra(
                'SELECT oid as id, source, target, length AS cost FROM tanzania_osm_edges',
                2785,
		2315,
		false
		) AS X
		ORDER BY seq)
update tanzania_osm_edges
set line = 'Central',
gauge = '1000',
status = 'open'
where oid in (select edge from tmp);

-- Central Line Kigoma port

with tmp as(
SELECT X.* FROM pgr_dijkstra(
                'SELECT oid as id, source, target, length AS cost FROM tanzania_osm_edges',
                2041,
		3413,
		false
		) AS X
		ORDER BY seq)
update tanzania_osm_edges
set line = 'Central',
gauge = '1000',
status = 'open',
mode = 'freight'
where oid in (select edge from tmp);

-- Mpanda Line - Kaliua-Mpanda
with tmp as(
SELECT X.* FROM pgr_dijkstra(
                'SELECT oid as id, source, target, length AS cost FROM tanzania_osm_edges',
                48,
		462,
		false
		) AS X
		ORDER BY seq)
update tanzania_osm_edges
set line = 'Mpanda',
gauge = '1000',
status = 'open'
where oid in (select edge from tmp);

-- Mwanza Line Tabora-Mwanza
with tmp as(
SELECT X.* FROM pgr_dijkstra(
                'SELECT oid as id, source, target, length AS cost FROM tanzania_osm_edges',
                10326,
		205,
		false
		) AS X
		ORDER BY seq)
update tanzania_osm_edges
set line = 'Mwanza',
gauge = '1000',
status = 'open'
where oid in (select edge from tmp);

-- Mwanza to Lake Ferries Terminal (disused)
with tmp as(
SELECT X.* FROM pgr_dijkstra(
                'SELECT oid as id, source, target, length AS cost FROM tanzania_osm_edges',
                205,
		1069,
		false
		) AS X
		ORDER BY seq)
update tanzania_osm_edges
set line = 'Mwanza-Lake Ferries Terminal',
gauge = '1000',
status = 'disused'
where oid in (select edge from tmp);

-- Singida Line Manyoni-Singida
with tmp as(
SELECT X.* FROM pgr_dijkstra(
                'SELECT oid as id, source, target, length AS cost FROM tanzania_osm_edges',
                2901,
		317,
		false
		) AS X
		ORDER BY seq)
update tanzania_osm_edges
set line = 'Singida',
gauge = '1000',
status = 'open'
where oid in (select edge from tmp);

-- need to prevent routing from disused Kilosa-Msolwa (1000mm) to Tazara line (1067mm) at Msolwa Station - break in gauge.
-- remove edge 
delete from tanzania_osm_edges
where oid = 3388

-- make an existing node Kilosa station for metre gauge - ensuring break in gauge
update tanzania_osm_nodes
set name = 'Msolwa Station',
gauge = '1000'
where oid = 3212

-- Kilosa-Msolwa (disused)
with tmp as(
SELECT X.* FROM pgr_dijkstra(
                'SELECT oid as id, source, target, length AS cost FROM tanzania_osm_edges',
                2901,
		3212,
		false
		) AS X
		ORDER BY seq)
update tanzania_osm_edges
set line = 'Kilosa-Msolwa',
gauge = '1000',
status = 'disused'
where oid in (select edge from tmp);

-- Link Line Ruvu to Tanga line
with tmp as(
SELECT X.* FROM pgr_dijkstra(
                'SELECT oid as id, source, target, length AS cost FROM tanzania_osm_edges',
                2585,
		1915,
		false
		) AS X
		ORDER BY seq)
update tanzania_osm_edges
set line = 'Link Line',
gauge = '1000',
status = 'open'
where oid in (select edge from tmp);

update tanzania_osm_nodes
set gauge = 'metre'
where st_intersects(geom, (select st_collect(geom) from tanzania_osm_edges where gauge = 'metre'))
and railway in ('station', 'halt', 'stop');

update tanzania_osm_nodes
set gauge = 'standard'
where st_intersects(geom, (select st_collect(geom) from tanzania_osm_edges where gauge = 'standard'))
and railway in ('station', 'halt', 'stop');

		
-- test routing		
		SELECT X.*, a.line, a.status, b.name FROM pgr_dijkstra(
                'SELECT oid as id, source, target, length AS cost FROM tanzania_osm_edges',
                2585,
		1915,
		false
		) AS X inner join
		tanzania_osm_edges as a on a.oid = X.edge left join
		tanzania_osm_nodes as b on b.oid = X.node
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
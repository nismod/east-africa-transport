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
UPDATE uganda_osm_edges set source = reverse(split_part(reverse(from_id), '_', 1))::int4;
UPDATE uganda_osm_edges set target = reverse(split_part(reverse(to_id), '_', 1))::int4;
UPDATE uganda_osm_edges set oid = reverse(split_part(reverse(id), '_', 1))::int4;

-- make primary key
ALTER TABLE uganda_osm_edges DROP CONSTRAINT uganda_osm_edges_pkey;
ALTER TABLE uganda_osm_edges ADD PRIMARY KEY (oid);

-- add oid column to nodes
ALTER TABLE uganda_osm_nodes ADD COLUMN oid int4;
UPDATE uganda_osm_nodes set oid = reverse(split_part(reverse(id), '_', 1))::int4;

-- make primary key
ALTER TABLE uganda_osm_nodes DROP CONSTRAINT uganda_osm_nodes_pkey;
ALTER TABLE uganda_osm_nodes ADD PRIMARY KEY (oid);

-- add columns to nodes
alter table uganda_osm_nodes
ADD COLUMN gauge text,
ADD COLUMN facility text; -- dry port, cargo terminus, gauge interchange


-- set additional node for stations
update uganda_osm_nodes
set name = '',
railway = 'station'
where oid = ;

-- facilities

-- dry port
update uganda_osm_nodes
set facility = 'dry port'
where oid in ();

-- gauge interchange
update uganda_osm_nodes
set facility = 'gauge freight interchange'
where oid in ();

-- cargo terminus
update uganda_osm_nodes
set facility = 'cargo terminus'
where oid in ();

-- duplicate stations
delete from uganda_osm_nodes
where oid IN ()

-- Update status - copy over from railway key if 'abandoned', 'disused'

UPDATE uganda_osm_edges
 SET status =
 CASE WHEN railway in ('abandoned', 'disused') THEN railway
 WHEN railway in ('rail') THEN 'open'
 else 'unknown'
 end;
 
 -- Update structure
 
 update uganda_osm_edges
 set structure = 
 CASE WHEN bridge = 'yes' then 'bridge'
 WHEN bridge = 'viaduct' then 'viaduct'
 WHEN railway in ('level_crossing', 'platform', 'station', 'traverser', 'turntable') THEN railway
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
(case when oid =  then ''
when oid =  then ''
else 'unnamed'
end)
where name is null and railway in ('station', 'stop', 'halt');

update uganda_osm_nodes
set name = '',
railway = 'stop',
facility = ''
where oid = ;

-- create new station nodes
-- this is required as there can be several edges running through stations but the station node
-- is located on an edge that isn't used for the route.

DO $$ DECLARE
-- create new station nodes
-- note: must not be a node coincident with the closest point (reassign that node as a station instead)
-- nodes INT ARRAY DEFAULT ARRAY [];
-- edges INT ARRAY DEFAULT ARRAY [];
 nodes INT ARRAY DEFAULT ARRAY [];
 edges INT ARRAY DEFAULT ARRAY [];
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
	tmp2 as ( select geom2 as geom, length, ( oid :: text || row_number ( ) over ( ) * 10000 ) :: int as oid, line, gauge, status, mode, structure, speed_freight, speed_passenger, comment, st_startpoint ( geom2 ), st_endpoint ( geom2 ) from tmp ) select
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

DO $$ DECLARE
-- edges INT ARRAY DEFAULT ARRAY [];
-- nodes INT ARRAY DEFAULT ARRAY [];
 edges INT ARRAY DEFAULT ARRAY [];
 nodes INT ARRAY DEFAULT ARRAY [];
edge INT;
node INT;
BEGIN
		for edge, node in select unnest(edges), unnest(nodes)
		LOOP
		raise notice'counter: %', edge || ' ' || node;
	insert into uganda_osm_edges with tmp as (select a.*, (st_dump(st_split(a.geom, b.geom))).geom as geom2 from uganda_osm_edges a, uganda_osm_nodes b where a.oid = edge and b.oid = node),
	tmp2 as (select geom2 as geom, length, ( oid :: text || row_number ( ) over ( ) * 10000 ) :: int as oid, line, gauge, status, mode, structure, speed_freight, speed_passenger, comment, st_startpoint ( geom2 ), st_endpoint ( geom2 ) from tmp ) select 
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
-- TAZARA (uganda)
-- from node 1236 (== 2271 in Tanzania network) to New Kapiri Mposhi (84)
with tmp as(
SELECT X.* FROM pgr_dijkstra(
                'SELECT oid as id, source, target, length AS cost FROM uganda_osm_edges',
                ,
		,
		false
		) AS X
		ORDER BY seq)
update uganda_osm_edges
set line = '',
gauge = '',
status = 'open',
mode = 'mixed'
where oid in (select edge from tmp);



-- update station gauge on stations

update uganda_osm_nodes
set gauge = ''
where st_intersects(geom, (select st_collect(geom) from uganda_osm_edges where gauge = '1067'))
and railway in ('station', 'halt', 'stop');


		
-- test routing		
		SELECT X.*, a.line, a.status, b.railway, b.name FROM pgr_dijkstra(
                'SELECT oid as id, source, target, length AS cost FROM uganda_osm_edges',
                1444,
		25,
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
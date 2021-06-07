-- pgRouting requires the source and target nodes to be integer ids.
-- Need to amend node and edge ids to integer

-- add souce and target columns
ALTER TABLE kenya_osm_edges
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
		
-- calculate edge lengths (need to transform to projected - use EPSG:32736)
UPDATE kenya_osm_edges set length = round(st_length(st_transform(geom, 32736))::numeric,2);

-- assume mixed mode unless amended
UPDATE kenya_osm_edges set mode = 'mixed';
		
-- copy integer ids component
UPDATE kenya_osm_edges set source = reverse(split_part(reverse(from_id), '_', 1))::int4;
UPDATE kenya_osm_edges set target = reverse(split_part(reverse(to_id), '_', 1))::int4;
UPDATE kenya_osm_edges set oid = reverse(split_part(reverse(id), '_', 1))::int4;

-- make primary key
ALTER TABLE kenya_osm_edges DROP CONSTRAINT kenya_osm_edges_pkey;
ALTER TABLE kenya_osm_edges ADD PRIMARY KEY (oid);

-- add oid column to nodes
ALTER TABLE kenya_osm_nodes ADD COLUMN oid int4;
UPDATE kenya_osm_nodes set oid = reverse(split_part(reverse(id), '_', 1))::int4;

-- make primary key
ALTER TABLE kenya_osm_nodes DROP CONSTRAINT kenya_osm_nodes_pkey;
ALTER TABLE kenya_osm_nodes ADD PRIMARY KEY (oid);

-- delete duplicate station nodes(on same gauge)
-- may just select those coincident with defined routes for export?

-- Ngong - delete oid 1343
-- Syokimau - delete oid 92
-- Imara Daima - delete oid 1
-- Maai Mahiu - delete 1347
-- Suswa - delete 1345
-- Emali - delete 1337
-- Voi - delete 1305

-- delete from kenya_osm_nodes where oid in (1343, 92, 1, 1347, 1345, 1337, 1305)

alter table kenya_osm_nodes
add COLUMN gauge text,
add COLUMN facility text; -- dry port, gauge interchange

-- update nodes values

-- set additional node for stations
update kenya_osm_nodes
set name = 'Nairobi Central Station',
railway = 'station'
where oid = 1699;

-- incorrect name
-- Jomo Kenyatta International Airport is Embakasi Village (bus available to JKIA from here)
-- different from the proposed airport rail link via Syokimau
update kenya_osm_nodes
set name = 'Embakasi Village'
where oid = 94;

-- amend Mombasa station node
UPDATE kenya_osm_nodes
SET name = 'Mombasa Terminus',
railway = 'station'
where oid = 956;

UPDATE kenya_osm_nodes
SET name = 'Old Mombasa Station',
railway = 'station'
where oid = 1512;

-- remove bad station node in middle of nowhere
delete from kenya_osm_nodes where oid = 730;

-- Update status - copy over from railway key if not 'rail' or 'narrow_gauge' or 'level_crossing' or 'platform' or 'station' or 'turntable'

UPDATE kenya_osm_edges
 SET status =
 CASE WHEN railway not in ('rail', 'narrow_gauge', 'level_crossing', 'platform', 'station', 'turntable') THEN railway
 else 'open'
 end;
 
 -- Update structure
 
 update kenya_osm_edges
 set structure = 
 CASE WHEN bridge = 'yes' then 'bridge'
 WHEN bridge = 'viaduct' then 'viaduct'
 WHEN railway in ('level_crossing', 'platform', 'station', 'turntable') THEN railway
 end;
 
-- populate gauge column
-- where railway = 'rail' gauge is standard as per OSM coding
update kenya_osm_edges
set gauge = '1435'
where railway = 'rail';

update kenya_osm_edges
set gauge = '1000'
where railway = 'narrow_gauge';

-- remove unused columns from edges
alter table kenya_osm_edges
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
alter table kenya_osm_nodes
drop column id,
drop column fid,
drop column osm_id,
drop column is_current;

-- update where name null and station/halt/stop
-- oid 1339 -> Taveta
-- oid 1341 -> Nanyuki
-- oid 205 -> Kiganjo
-- oid 286 -> Equator
-- oid 340 -> Moi's Bridge
-- oid 476 -> Webuye
-- otherwise unnamed

update kenya_osm_nodes
set name = 
(case when oid = 1339 then 'Taveta'
when oid = 1341 then 'Nanyuki'
when oid = 205 then 'Kiganjo'
when oid = 286 then 'Equator'
when oid = 340 then 'Moi''s Bridge'
when oid = 476 then 'Webuye'
else 'unnamed'
end)
where name is null and railway in ('station', 'stop', 'halt');

-- facilities
update kenya_osm_nodes
set facility = 'Inland Container Port Nairobi',
railway = 'stop'
where oid = 3126;

update kenya_osm_nodes
set facility = 'Inland Container Depot Kisumu',
railway = 'stop'
where oid = 1835;

update kenya_osm_nodes
set facility = 'Inland Container Depot Naivasha',
railway = 'stop'
where oid = 1259;

update kenya_osm_nodes
set facility = 'Mombasa Port',
railway = 'stop'
where oid = 3191;

update kenya_osm_nodes
set facility = 'Mombasa Port',
railway = 'stop'
where oid = 2489;

-- create new station nodes
-- this is required as there can be several edges running through stations but the station node
-- is located on an edge that isn't used for the route.

-- Kajiado Railway Station 437 -> 1097
-- Kima 1304 -> 2071
-- Kibwezi Station 1350 -> 1543
-- Tsavo 700 -> 2044
-- Voi Station 1349 -> 1477
-- Miasenyi Station 1348 -> 1452
-- Mgalani 699 -> 2028
-- Malaba 164 -> 291
-- Eldoret 217 -> 2419
-- Kipkarren 336 -> 939

DO $$ DECLARE
-- create new station nodes
-- note: must not be a node coincident with the closest point (reassign that node as a station instead)
nodes INT ARRAY DEFAULT ARRAY [437, 1304, 1350, 700,  1349, 1348, 699,  164, 217,  336 ];
edges INT ARRAY DEFAULT ARRAY [1097, 2071, 1543, 2044, 1477, 1452, 2028, 291, 2419, 939 ];
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
SELECT ST_LineLocateN(e.geom, n.geom) from kenya_osm_nodes n, kenya_osm_edges e where n.oid = node and e.oid = edge
into idx;
-- closest point
select ST_ClosestPoint(e.geom, n.geom) from kenya_osm_nodes n, kenya_osm_edges e where n.oid = node and e.oid = edge into closest_point;
-- new line geometry with added point
select ST_AddPoint(e.geom, closest_point, idx) from kenya_osm_edges e where e.oid = edge into newline;
-- original source and target
select target from kenya_osm_edges where oid = edge into ortarget;
select source from kenya_osm_edges where oid = edge into orsource;

raise notice 'counter: %', node || ' ' || edge || ' ' || idx || ' ' || orsource || ' ' || ortarget ;	

-- create new node for station
INSERT INTO kenya_osm_nodes (name, geom, railway, oid)
SELECT name, closest_point, railway, oid + 10000
FROM kenya_osm_nodes
WHERE oid = node;
 
insert into kenya_osm_edges 
with tmp as ( select a.*, ( st_dump ( st_split ( newline, closest_point ) ) ).geom as geom2 from kenya_osm_edges a where oid = edge ),
	tmp2 as ( select geom2 as geom, length, ( oid :: text || row_number ( ) over ( ) * 10000 ) :: int as oid, line, gauge, status, mode, structure, speed_freight, speed_passenger, comment, st_startpoint ( geom2 ), st_endpoint ( geom2 ) from tmp ) select
	a.geom,
	round( st_length ( st_transform ( a.geom, 32736 ) ) :: numeric, 2 ) as length,
	b.oid as source,
	c.oid as target,
	a.oid,
	line,
	gauge,
	status,
	mode,
	structure,
	speed_freight,
	speed_passenger,
	comment
	from
		tmp2 a JOIN kenya_osm_nodes b ON st_dwithin( b.geom, a.st_startpoint, .000000001 )
		-- need st_dwithin rather than st_intersects 
		JOIN kenya_osm_nodes c ON st_dwithin ( c.geom, a.st_endpoint, .00000000001 )
		-- there can be additional nodes than the original target and source nodes at the original line end /start points
		-- so have to limit results 
		where b.oid in (ortarget, orsource) or c.oid in (ortarget,orsource)
	;
	
	-- delete the original edge
	delete 
	from
	kenya_osm_edges 
	where
	oid = edge;
	
	-- delete original station node
	-- don't think will do that, will just select the station nodes that intersect the required routes.
	-- delete 
	-- from
	-- kenya_osm_nodes 
	-- where
	-- oid = node;
	

END LOOP;
END $$;


-- psql code to fix routing issue. Splits edge at node.
-- narrow-gauge
-- allow routing between Nairobi terminal and Nairobi in metre gauge line
-- split 2553 at 3084
-- split 2554 at 2756
-- allow routing from Nairobi Terminus to Naivasha
-- split 1525 at 3139
-- allow routing to old Mombasa Station via Tudor Creek
-- split 141 at 1517
-- allow routing of Changamwe-Kilindini freight
-- split 236 at 2497
-- split 1781 at 2488
-- allow routing between Eldoret and Malaba
-- split 495 at 3013
-- allow routing between Kisumu and Butere
-- split 149 at 2215
-- allow routing between Gilgil and Nyahururu
-- split 1166 at 1826
-- allow routing between Rongai and Solai
-- split  179 at 1691
-- allow routing between Eldoret and Kitale
-- split 2374 at 2820
-- allow routing between Makadara and Nanyuki
-- split 2551 at 3109
-- allow routing from Nakuru-Kisumu to Chemelil town
-- split 519 at 2159
-- allow routing from Voi to Taveta
-- split 1289 at 1978
-- SGR
-- allow routing out of Mombasa Terminus
-- split 1587 at 2296
-- split 1586 at 2819
-- routing out/in Imara and old Mombasa line
-- split 2000 at 2757
-- allow routing into Kisumu Inland Container Depot
-- split 1661 at 1834
-- allow routing into Naivasha Inland Container Depot
-- split 2283 at 2887


DO $$ DECLARE
-- edges INT ARRAY DEFAULT ARRAY [2553, 2554, 1525, 141,  236,  1781, 495, 149,  1166, 179,  2374, 2551, 519,  1289, 1587, 1586, 2000, 1661, 2283 ];
-- nodes INT ARRAY DEFAULT ARRAY [3084, 2756, 3139, 1517, 2497, 2488, 3013, 2215, 1826, 1691, 2820, 3109, 2159, 1978, 2296, 2819, 2757, 1834, 2887 ];
edges INT ARRAY DEFAULT ARRAY [2283 ];
nodes INT ARRAY DEFAULT ARRAY [2887 ];
edge INT;
node INT;
BEGIN
		for edge, node in select unnest(edges), unnest(nodes)
		LOOP
		raise notice'counter: %', edge || ' ' || node;
	insert into kenya_osm_edges with tmp as (select a.*, (st_dump(st_split(a.geom, b.geom))).geom as geom2 from kenya_osm_edges a, kenya_osm_nodes b where a.oid = edge and b.oid = node),
	tmp2 as (select geom2 as geom, length, ( oid :: text || row_number ( ) over ( ) * 10000 ) :: int as oid, line, gauge, status, mode, structure, speed_freight, speed_passenger, comment, st_startpoint ( geom2 ), st_endpoint ( geom2 ) from tmp ) select 
	a.geom,
	round( st_length ( st_transform ( a.geom, 32736 ) ) :: numeric, 2 ) as length,
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
	a.comment 
	from
		tmp2
		a JOIN kenya_osm_nodes b ON st_intersects ( b.geom, a.st_startpoint )
		JOIN kenya_osm_nodes c ON st_intersects ( c.geom, a.st_endpoint );
	delete 
	from
		kenya_osm_edges 
	where
		oid = edge;
END LOOP;
END $$;

-- connect the NICD Longonot line to the metre gauge at - add node 290  to beginning of line 2532 (positon zero) and change source to 290
UPDATE kenya_osm_edges
	SET geom = ST_AddPoint(geom, (select geom from kenya_osm_nodes where oid = 290), 0),
	source = 290,
	gauge = '1000',
	line = 'NICD - Longonot Railway Link'
   WHERE oid = 2532;
-- update
UPDATE kenya_osm_edges
	SET length = round(st_length(st_transform(geom, 32736))::numeric,2)
	WHERE oid = 2532;

-- gap in edge on Magadi line. Extend line 1106 to node 2801
UPDATE kenya_osm_edges
	SET geom = ST_AddPoint(geom, (select geom from kenya_osm_nodes where oid = 2801), st_npoints(geom)),
	target = 2801
   WHERE oid = 1106;
		
-- Update line information
-- metre gauge lines	
		
-- Makadara to Nanyuki

with tmp as(
SELECT X.* FROM pgr_dijkstra(
                'SELECT oid as id, source, target, length AS cost FROM kenya_osm_edges',
                348,
		246,
		false
		) AS X
		ORDER BY seq)
update kenya_osm_edges
set line = 'Makadara-Nanyuki'
where oid in (select edge from tmp);

-- Mombassa to Nairobi

with tmp as(
SELECT X.* FROM pgr_dijkstra(
                'SELECT oid as id, source, target, length AS cost FROM kenya_osm_edges',
                1512,
		1699,
		false
		) AS X
		ORDER BY seq)
update kenya_osm_edges
set line = 'Mombassa-Nairobi'
where oid in (select edge from tmp);
		
-- Mobassa to Nairobi is disused as of April 2017 - except for Nairobi Terminus to Nairobi city centre
with tmp as(
SELECT X.* FROM pgr_dijkstra(
                'SELECT oid as id, source, target, length AS cost FROM kenya_osm_edges',
                1512,
		93,
		false
		) AS X
		ORDER BY seq)
update kenya_osm_edges
set status = 'disused'
where oid in (select edge from tmp);

-- Changamwe to Chaani Oil Refinery and Kilindini Harbour - freight
with tmp as(
SELECT X.* FROM pgr_dijkstra(
                'SELECT oid as id, source, target, length AS cost FROM kenya_osm_edges',
                1517,
		2489,
		false
		) AS X
		ORDER BY seq)
update kenya_osm_edges
set status = 'disused',
mode = 'freight',
line = 'Changamwe-Kilindini'
where oid in (select edge from tmp);


-- Nanyuki to Malaba (border with Uganda oid 1632 joins to 915) 
with tmp as(
SELECT X.* FROM pgr_dijkstra(
                'SELECT oid as id, source, target, length AS cost FROM kenya_osm_edges',
                1520,
		1632,
		false
		) AS X
		ORDER BY seq)
update kenya_osm_edges
set line = 'Nakuru-Malaba'
where oid in (select edge from tmp);

UPDATE kenya_osm_edges
	SET gauge = '1000',
	status = 'rehabilitation',
	comment = 'Currently out of use, rehabilitation due to be completed September 2021'
	WHERE line = 'Nakuru-Malaba';


-- Nanyuki to Kisumu
with tmp as(
SELECT X.* FROM pgr_dijkstra(
                'SELECT oid as id, source, target, length AS cost FROM kenya_osm_edges',
                1520,
		663,
		false
		) AS X
		ORDER BY seq)
update kenya_osm_edges
set line = 'Nakuru-Kisumu'
where oid in (select edge from tmp);
		
-- Kisumu to Butere
with tmp as(
SELECT X.* FROM pgr_dijkstra(
                'SELECT oid as id, source, target, length AS cost FROM kenya_osm_edges',
                2215,
		1792,
		false
		) AS X
		ORDER BY seq)
update kenya_osm_edges
set line = 'Kisumu-Butere'
where oid in (select edge from tmp);

-- Rongai to Solai
with tmp as(
SELECT X.* FROM pgr_dijkstra(
                'SELECT oid as id, source, target, length AS cost FROM kenya_osm_edges',
                1691,
		1690,
		false
		) AS X
		ORDER BY seq)
update kenya_osm_edges
set line = 'Rongai-Solai'
where oid in (select edge from tmp);

UPDATE kenya_osm_edges
	SET gauge = '1000'
	WHERE line = 'Rongai-Solai';


-- Gilgil to Nyahururu
with tmp as(
SELECT X.* FROM pgr_dijkstra(
                'SELECT oid as id, source, target, length AS cost FROM kenya_osm_edges',
                1826,
		1829,
		false
		) AS X
		ORDER BY seq)
update kenya_osm_edges
set line = 'Gilgil-Nyahururu'
where oid in (select edge from tmp);

UPDATE kenya_osm_edges
	SET gauge = '1000'
	WHERE line = 'Gilgil-Nyahururu';
		
-- Eldoret to Kitale
with tmp as(
SELECT X.* FROM pgr_dijkstra(
                'SELECT oid as id, source, target, length AS cost FROM kenya_osm_edges',
                2820,
		2095,
		false
		) AS X
		ORDER BY seq)
update kenya_osm_edges
set line = 'Eldoret-Kitale'
where oid in (select edge from tmp);

UPDATE kenya_osm_edges
	SET gauge = '1000'
	WHERE line = 'Eldoret-Kitale';
	
-- branch to Chemelil town
with tmp as(
SELECT X.* FROM pgr_dijkstra(
                'SELECT oid as id, source, target, length AS cost FROM kenya_osm_edges',
                2159,
		2160,
		false
		) AS X
		ORDER BY seq)
update kenya_osm_edges
set line = 'Chemelil branch'
where oid in (select edge from tmp);		

UPDATE kenya_osm_edges
	SET gauge = '1000'
	WHERE line = 'Chemelil branch';
	
-- from Nairobi to Nakuru
with tmp as(
SELECT X.* FROM pgr_dijkstra(
                'SELECT oid as id, source, target, length AS cost FROM kenya_osm_edges',
                1699,
		1520,
		false
		) AS X
		ORDER BY seq)
update kenya_osm_edges
set line = 'Nairobi-Nakuru'
where oid in (select edge from tmp);		
	
-- from Konza to Magadi
with tmp as(
SELECT X.* FROM pgr_dijkstra(
                'SELECT oid as id, source, target, length AS cost FROM kenya_osm_edges',
                1244,
		2868,
		false
		) AS X
		ORDER BY seq)
update kenya_osm_edges
set line = 'Konza-Magadi'
where oid in (select edge from tmp);		

		
-- from Voi to Taveta
with tmp as(
SELECT X.* FROM pgr_dijkstra(
                'SELECT oid as id, source, target, length AS cost FROM kenya_osm_edges',
                1978,
		1979,
		false
		) AS X
		ORDER BY seq)
update kenya_osm_edges
set line = 'Voi-Taveta',
gauge = '1000'
where oid in (select edge from tmp);			

-- SGR lines
-- from Mombasa-Nairobi SGR
with tmp as(
SELECT X.* FROM pgr_dijkstra(
                'SELECT oid as id, source, target, length AS cost FROM kenya_osm_edges',
                956,
		1228,
		false
		) AS X
		ORDER BY seq)
update kenya_osm_edges
set line = 'Mombasa-Nairobi SGR',
gauge = '1435'
where oid in (select edge from tmp);		

-- 	Mombasa-Nairobi SGR freight only
with tmp as(
SELECT X.* FROM pgr_dijkstra(
                'SELECT oid as id, source, target, length AS cost FROM kenya_osm_edges',
                956,
		3191,
		false
		) AS X
		ORDER BY seq)
update kenya_osm_edges
set line = 'Mombasa-Nairobi SGR',
gauge = '1435',
mode = 'freight'
where oid in (select edge from tmp);		

-- also at Nairobi

-- Nairobi-Naivasha (Suswa) SGR
with tmp as(
SELECT X.* FROM pgr_dijkstra(
                'SELECT oid as id, source, target, length AS cost FROM kenya_osm_edges',
                1228,
		1229,
		false
		) AS X
		ORDER BY seq)
update kenya_osm_edges
set line = 'Nairobi-Naivasha SGR',
gauge = '1435'
where oid in (select edge from tmp);		

-- Naivasha (Suswa) - Kisumu SGR
with tmp as(
SELECT X.* FROM pgr_dijkstra(
                'SELECT oid as id, source, target, length AS cost FROM kenya_osm_edges',
                1229,
		714,
		false
		) AS X
		ORDER BY seq)
update kenya_osm_edges
set line = 'Naivasha-Kisumu SGR',
gauge = '1435'
where oid in (select edge from tmp);		

-- Nairobi Terminus to Inland Port - freight only
with tmp as(
SELECT X.* FROM pgr_dijkstra(
                'SELECT oid as id, source, target, length AS cost FROM kenya_osm_edges',
                2845,
		3126,
		false
		) AS X
		ORDER BY seq)
update kenya_osm_edges
set line = 'Nairobi Terminus-Inland Container Port Nairobi SGR',
gauge = '1435',
mode = 'freight'
where oid in (select edge from tmp);		

-- Kibos - Kisumu Inland Container Port
with tmp as(
SELECT X.* FROM pgr_dijkstra(
                'SELECT oid as id, source, target, length AS cost FROM kenya_osm_edges',
                1834,
		1835,
		false
		) AS X
		ORDER BY seq)
update kenya_osm_edges
set line = 'Kibos - Kisumu Inland Container Port',
gauge = '1000',
mode = 'freight',
status = 'open'
where oid in (select edge from tmp);

-- Naivasha Inland Container Depot
with tmp as(
SELECT X.* FROM pgr_dijkstra(
                'SELECT oid as id, source, target, length AS cost FROM kenya_osm_edges',
                2887,
		1259,
		false
		) AS X
		ORDER BY seq)
update kenya_osm_edges
set line = 'Naivasha Inland Container Port',
gauge = '1435',
mode = 'freight',
status = 'open'
where oid in (select edge from tmp);

-- Embakasi Village - Nairobi
with tmp as(
SELECT X.* FROM pgr_dijkstra(
                'SELECT oid as id, source, target, length AS cost FROM kenya_osm_edges',
                1480,
		2849,
		false
		) AS X
		ORDER BY seq)
update kenya_osm_edges
set line = 'Embakasi Village',
gauge = '1000',
status = 'open'
where oid in (select edge from tmp);


-- Syokimau
with tmp as(
SELECT X.* FROM pgr_dijkstra(
                'SELECT oid as id, source, target, length AS cost FROM kenya_osm_edges',
                1330,
		2757,
		false
		) AS X
		ORDER BY seq)
update kenya_osm_edges
set line = 'Syokimau',
gauge = '1000',
status = 'open'
where oid in (select edge from tmp);

-- update station gauge

update kenya_osm_nodes
set gauge = '1000'
where st_intersects(geom, (select st_collect(geom) from kenya_osm_edges where gauge = '1000'))
and railway in ('station', 'halt', 'stop');

update kenya_osm_nodes
set gauge = '1435'
where st_intersects(geom, (select st_collect(geom) from kenya_osm_edges where gauge = '1435'))
and railway in ('station', 'halt', 'stop');

		
-- test routing		
		SELECT X.*, a.line, a.status, b.name FROM pgr_dijkstra(
                'SELECT oid as id, source, target, length AS cost FROM kenya_osm_edges',
                178,
		1330,
		false
		) AS X inner join
		kenya_osm_edges as a on a.oid = X.edge left join
		kenya_osm_nodes as b on b.oid = X.node
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
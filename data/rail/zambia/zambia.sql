-- pgRouting requires the source and target nodes to be integer ids.
-- Need to amend node and edge ids to integer

-- add souce and target columns
ALTER TABLE zambia_osm_edges
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
UPDATE zambia_osm_edges set length = round(st_length(st_transform(geom, 21036))::numeric,2);

-- assume mixed mode unless amended
UPDATE zambia_osm_edges set mode = 'mixed';
		
-- copy integer ids component
-- zambia ids start 3330000
UPDATE zambia_osm_edges set source = 3330000 + reverse(split_part(reverse(from_id), '_', 1))::int4;
UPDATE zambia_osm_edges set target = 3330000 + reverse(split_part(reverse(to_id), '_', 1))::int4;
UPDATE zambia_osm_edges set oid = 3330000 + reverse(split_part(reverse(id), '_', 1))::int4;

-- make primary key
ALTER TABLE zambia_osm_edges DROP CONSTRAINT zambia_osm_edges_pkey;
ALTER TABLE zambia_osm_edges ADD PRIMARY KEY (oid);

-- add oid column to nodes
ALTER TABLE zambia_osm_nodes ADD COLUMN oid int4;
UPDATE zambia_osm_nodes set oid = 3330000 + reverse(split_part(reverse(id), '_', 1))::int4;

-- make primary key
ALTER TABLE zambia_osm_nodes DROP CONSTRAINT zambia_osm_nodes_pkey;
ALTER TABLE zambia_osm_nodes ADD PRIMARY KEY (oid);

-- add columns to nodes
alter table zambia_osm_nodes
ADD COLUMN gauge text,
ADD COLUMN facility text; -- dry_port, gauge_interchange, quarry, mine


-- set additional node for stations
update zambia_osm_nodes
set name = 'Kataba',
railway = 'station'
where oid = 3330796;

-- Update status - copy over from railway key if 'abandoned', 'disused'

UPDATE zambia_osm_edges
 SET status =
 CASE WHEN railway in ('abandoned', 'disused') THEN railway
 WHEN railway in ('rail') THEN 'open'
 else 'unknown'
 end;
 
 -- Update structure
 
 update zambia_osm_edges
 set structure = 
 CASE WHEN bridge = 'yes' then 'bridge'
 WHEN bridge = 'viaduct' then 'viaduct'
 WHEN railway in ('level_crossing', 'platform', 'station', 'traverser', 'turntable') THEN railway
 end;
 
 
-- populate gauge column
-- incorrectly coded rail in OSM data. This will need to be set per route.

-- remove unused columns from edges
alter table zambia_osm_edges
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
alter table zambia_osm_nodes
drop column id,
drop column fid,
drop column osm_id,
drop column is_current;

-- update where name null and station/halt/stop
-- otherwise unnamed

update zambia_osm_nodes
set name = 
(case when oid = 3330025 then 'Luanshya'
when oid = 3330423 then 'Simonga'
when oid = 3330490 then 'Makunka'
when oid = 3330093 then 'Lunsemfwa'
when oid = 3330083 then 'Mkushi River'
when oid = 3330078 then 'Finkuli'
when oid = 3330309 then 'Luslwasi'
when oid = 3330511 then 'Kanona'
when oid = 3330510 then 'Chakalamo'
when oid = 3330074 then 'Chilonga'
when oid = 3330512 then 'Kapoko'
when oid = 3330352 then 'Kungu'
else 'unnamed'
end)
where name is null and railway in ('station', 'stop', 'halt');

update zambia_osm_nodes
set name = 'Ndola Lime Company',
railway = 'stop',
facility = 'quarry'
where oid = 3331118;

update zambia_osm_nodes
set name = 'KCM Nkana Refinery',
railway = 'stop',
facility = 'refinery'
where oid = 3331417;

update zambia_osm_nodes
set name = 'KCM Nchanga Copper Mine',
railway = 'stop',
facility = 'mine'
where oid = 3331740;

update zambia_osm_nodes
set name = 'KCM Konkola Copper Mine',
railway = 'stop',
facility = 'mine'
where oid = 3331730;


-- create new station nodes
-- this is required as there can be several edges running through stations but the station node
-- is located on an edge that isn't used for the route.

-- Chipata 3330300 to 3330554
-- Kapiri Mposhi (ZR) 3330561 to 33301825
-- Chikonkomene Siding 3330627 - 3330445
-- Kasavasa Siding 3330628 - 3330473
-- Chambeshi 3330317 to 3330135

DO $$ DECLARE
-- create new station nodes
-- note: must not be a node coincident with the closest point (reassign that node as a station instead)
nodes INT ARRAY DEFAULT ARRAY [3330300, 3330561, 3330627, 3330628, 3330317];
edges INT ARRAY DEFAULT ARRAY [3330554, 3331825, 3330445, 3330473, 3330135];
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
SELECT ST_LineLocateN(e.geom, n.geom) from zambia_osm_nodes n, zambia_osm_edges e where n.oid = node and e.oid = edge
into idx;
-- closest point
select ST_ClosestPoint(e.geom, n.geom) from zambia_osm_nodes n, zambia_osm_edges e where n.oid = node and e.oid = edge into closest_point;
-- new line geometry with added point
select ST_AddPoint(e.geom, closest_point, idx) from zambia_osm_edges e where e.oid = edge into newline;
-- original source and target
select target from zambia_osm_edges where oid = edge into ortarget;
select source from zambia_osm_edges where oid = edge into orsource;

raise notice 'counter: %', node || ' ' || edge || ' ' || idx || ' ' || orsource || ' ' || ortarget ;	

-- create new node for station
INSERT INTO zambia_osm_nodes (name, geom, railway, oid)
SELECT name, closest_point, railway, oid + 10000
FROM zambia_osm_nodes
WHERE oid = node;
 
insert into zambia_osm_edges 
with tmp as ( select a.*, ( st_dump ( st_split ( newline, closest_point ) ) ).geom as geom2 from zambia_osm_edges a where oid = edge ),
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
		tmp2 a JOIN zambia_osm_nodes b ON st_dwithin( b.geom, a.st_startpoint, .000000001 )
		-- need st_dwithin rather than st_intersects 
		JOIN zambia_osm_nodes c ON st_dwithin ( c.geom, a.st_endpoint, .00000000001 )
		-- there can be additional nodes than the original target and source nodes at the original line end /start points
		-- so have to limit results 
		where b.oid in (ortarget, orsource) or c.oid in (ortarget,orsource)
	;
	
	-- delete the original edge
	delete 
	from
	zambia_osm_edges 
	where
	oid = edge;
	
	-- delete original station node
	-- don't think will do that, will just select the station nodes that intersect the required routes.
	-- delete 
	-- from
	-- zambia_osm_nodes 
	-- where
	-- oid = node;
	

END LOOP;
END $$;


-- psql code to fix routing issue. Splits edge at node.

-- allow routing onto the Mulobezi Railway
-- split 3331808 at 3331112
-- allow routing onto Mufulira branch
-- split 333852 at 3331218
-- allow routing to Ndola Lime Quary
-- split 3331391 at 3331117
-- split 3331377 at 3331444
-- allow routing to KCM Nkana refinery
-- split 3331815 at 3331380
-- split 3330816 at 3331382
-- 3330814 at 3331416
-- allow routing Konkola Mine
-- 3331543 at 3331725
DO $$ DECLARE
 edges INT ARRAY DEFAULT ARRAY [3331808, 3330852, 3331391, 3331377, 3331815, 3330816, 3330814, 3331543];
 nodes INT ARRAY DEFAULT ARRAY [3331112, 3331218, 3331117, 3331444, 3331380, 3331382, 3331416, 3331725];
-- edges INT ARRAY DEFAULT ARRAY [];
-- nodes INT ARRAY DEFAULT ARRAY [];
edge INT;
node INT;
BEGIN
		for edge, node in select unnest(edges), unnest(nodes)
		LOOP
		raise notice'counter: %', edge || ' ' || node;
	insert into zambia_osm_edges with tmp as (select a.*, (st_dump(st_split(a.geom, b.geom))).geom as geom2 from zambia_osm_edges a, zambia_osm_nodes b where a.oid = edge and b.oid = node),
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
		a JOIN zambia_osm_nodes b ON st_intersects ( b.geom, a.st_startpoint )
		JOIN zambia_osm_nodes c ON st_intersects ( c.geom, a.st_endpoint );
	delete 
	from
		zambia_osm_edges 
	where
		oid = edge;
END LOOP;
END $$;

-- routes
-- TAZARA (Zambia)
-- from node 3331236 (== 2222271 in Tanzania network) to New Kapiri Mposhi (3330084)
with tmp as(
SELECT X.* FROM pgr_dijkstra(
                'SELECT oid as id, source, target, length AS cost FROM zambia_osm_edges',
                3331236,
		3330084,
		false
		) AS X
		ORDER BY seq)
update zambia_osm_edges
set line = 'TAZARA (Zambia)',
gauge = '1067',
status = 'open',
mode = 'mixed'
where oid in (select edge from tmp);

-- TAZARA - Kapiri Mposhi Junction
-- Freight only
-- See: https://constructionreviewonline.com/news/zambia-signs-us-825m-railway-lines-upgrade-contract/
-- North
with tmp as(
SELECT X.* FROM pgr_dijkstra(
                'SELECT oid as id, source, target, length AS cost FROM zambia_osm_edges',
                3330084,
		3331256,
		false
		) AS X
		ORDER BY seq)
update zambia_osm_edges
set line = 'TAZARA - Kapiri Mposhi Junction',
gauge = '1067',
status = 'open',
mode = 'freight'
where oid in (select edge from tmp);

--South
with tmp as(
SELECT X.* FROM pgr_dijkstra(
                'SELECT oid as id, source, target, length AS cost FROM zambia_osm_edges',
                3330084,
		3331239,
		false
		) AS X
		ORDER BY seq)
update zambia_osm_edges
set line = 'TAZARA - Kapiri Mposhi Junction',
gauge = '1067',
status = 'open',
mode = 'freight'
where oid in (select edge from tmp);

-- Zambian Railways
-- from Victoria Falls Bridge (Zimbabwe Border) - Ndola
with tmp as(
SELECT X.* FROM pgr_dijkstra(
                'SELECT oid as id, source, target, length AS cost FROM zambia_osm_edges',
                3331111,
		3331829,
		false
		) AS X
		ORDER BY seq)
update zambia_osm_edges
set line = 'Livingstone - Ndola',
gauge = '1067',
status = 'open',
mode = 'mixed'
where oid in (select edge from tmp);

-- Ndola - DRC border
with tmp as(
SELECT X.* FROM pgr_dijkstra(
                'SELECT oid as id, source, target, length AS cost FROM zambia_osm_edges',
                3330010,
		3331227,
		false
		) AS X
		ORDER BY seq)
update zambia_osm_edges
set line = 'Ndola - DRC border',
gauge = '1067',
status = 'open',
mode = 'mixed'
where oid in (select edge from tmp);

-- Mulobezi Railway
with tmp as(
SELECT X.* FROM pgr_dijkstra(
                'SELECT oid as id, source, target, length AS cost FROM zambia_osm_edges',
                3331112,
		3330486,
		false
		) AS X
		ORDER BY seq)
update zambia_osm_edges
set line = 'Mulobezi Railway',
gauge = '1067',
status = 'open',
mode = 'mixed'
where oid in (select edge from tmp);

-- Mulobezi - Kataba (abandoned)
with tmp as(
SELECT X.* FROM pgr_dijkstra(
                'SELECT oid as id, source, target, length AS cost FROM zambia_osm_edges',
                3332430,
		3330796,
		false
		) AS X
		ORDER BY seq)
update zambia_osm_edges
set line = 'Mulobezi - Kataba',
gauge = '1067',
status = 'abandoned',
mode = 'mixed'
where oid in (select edge from tmp);

-- simplify network - add line to link Choma with Maamba Colliery Railway (Choma - Masuku)
with tmp as
(
select st_makeline(a.geom, b.geom) as line from zambia_osm_nodes a, zambia_osm_nodes b where a.oid = 3330130 and b.oid = 3330418
)
insert into zambia_osm_edges select 
a.line,
round( st_length ( st_transform ( a.line, 21036 ) ) :: numeric, 2 ) as length,
3330130,
3330418,
3350000
from tmp as a;

-- Choma - Masuka (Maamba Colliery Railway)
with tmp as(
SELECT X.* FROM pgr_dijkstra(
                'SELECT oid as id, source, target, length AS cost FROM zambia_osm_edges',
                3330130,
		3330214,
		false
		) AS X
		ORDER BY seq)
update zambia_osm_edges
set line = 'Choma - Masuka (Maamba Colliery Railway)',
gauge = '1067',
status = 'open',
mode = 'mixed'
where oid in (select edge from tmp);


-- Chipata - Malawi Border (to Mchingi)
with tmp as(
SELECT X.* FROM pgr_dijkstra(
                'SELECT oid as id, source, target, length AS cost FROM zambia_osm_edges',
                3340300,
		3330168,
		false
		) AS X
		ORDER BY seq)
update zambia_osm_edges
set line = 'Chipata - Malawi (to Mchingi)',
gauge = '1067',
status = 'open',
mode = 'mixed'
where oid in (select edge from tmp);

-- Ndola - Chingola
with tmp as(
SELECT X.* FROM pgr_dijkstra(
                'SELECT oid as id, source, target, length AS cost FROM zambia_osm_edges',
                3331829,
		3330365,
		false
		) AS X
		ORDER BY seq)
update zambia_osm_edges
set line = 'Ndola - Chingola',
gauge = '1067',
status = 'open',
mode = 'mixed'
where oid in (select edge from tmp);

-- Mufulira branch
with tmp as(
SELECT X.* FROM pgr_dijkstra(
                'SELECT oid as id, source, target, length AS cost FROM zambia_osm_edges',
                3331218,
		3330506,
		false
		) AS X
		ORDER BY seq)
update zambia_osm_edges
set line = 'Mufulira branch line',
gauge = '1067',
status = 'open',
mode = 'mixed'
where oid in (select edge from tmp);

-- Chililabombwe branch
with tmp as(
SELECT X.* FROM pgr_dijkstra(
                'SELECT oid as id, source, target, length AS cost FROM zambia_osm_edges',
                3331429,
		3330504,
		false
		) AS X
		ORDER BY seq)
update zambia_osm_edges
set line = 'Chililabombwe branch line',
gauge = '1067',
status = 'open',
mode = 'mixed'
where oid in (select edge from tmp);

-- Nodola - Ndola Lime Company
with tmp as(
SELECT X.* FROM pgr_dijkstra(
                'SELECT oid as id, source, target, length AS cost FROM zambia_osm_edges',
                3331444,
		3331118,
		false
		) AS X
		ORDER BY seq)
update zambia_osm_edges
set line = 'Ndola - Ndola Lime Quarry',
gauge = '1067',
status = 'open',
mode = 'freight'
where oid in (select edge from tmp);

-- Nkana Copper Refinery
with tmp as(
SELECT X.* FROM pgr_dijkstra(
                'SELECT oid as id, source, target, length AS cost FROM zambia_osm_edges',
                3331375,
		3331417,
		false
		) AS X
		ORDER BY seq)
update zambia_osm_edges
set line = 'Nkana Copper Refinery',
gauge = '1067',
status = 'open',
mode = 'freight'
where oid in (select edge from tmp);

-- Nchanga Copper Mine
with tmp as(
SELECT X.* FROM pgr_dijkstra(
                'SELECT oid as id, source, target, length AS cost FROM zambia_osm_edges',
                3330365,
		3331740,
		false
		) AS X
		ORDER BY seq)
update zambia_osm_edges
set line = 'Nchanga Copper Mine',
gauge = '1067',
status = 'open',
mode = 'freight'
where oid in (select edge from tmp);

-- Konkola Copper Mine
with tmp as(
SELECT X.* FROM pgr_dijkstra(
                'SELECT oid as id, source, target, length AS cost FROM zambia_osm_edges',
                3330504,
		3331730,
		false
		) AS X
		ORDER BY seq)
update zambia_osm_edges
set line = 'Konkola Copper Mine',
gauge = '1067',
status = 'open',
mode = 'freight'
where oid in (select edge from tmp);

-- Ndola to Luanshya
-- this is abandoned (needs recosntruction) and has a few missing edges
-- complete lines for routing purposes
with tmp as
(
select st_makeline(a.geom, b.geom) as line from zambia_osm_nodes a, zambia_osm_nodes b where a.oid = 3332437 and b.oid = 3331444
)
insert into zambia_osm_edges select 
a.line,
round( st_length ( st_transform ( a.line, 21036 ) ) :: numeric, 2 ) as length,
3332437,
3331444,
3350001
from tmp as a; 

with tmp as
(
select st_makeline(a.geom, b.geom) as line from zambia_osm_nodes a, zambia_osm_nodes b where a.oid = 3332438 and b.oid = 3332439
)
insert into zambia_osm_edges select 
a.line,
round( st_length ( st_transform ( a.line, 21036 ) ) :: numeric, 2 ) as length,
3332438,
3332439,
3350002
from tmp as a; 

with tmp as
(
select st_makeline(a.geom, b.geom) as line from zambia_osm_nodes a, zambia_osm_nodes b where a.oid = 3332440 and b.oid = 3331436
)
insert into zambia_osm_edges select 
a.line,
round( st_length ( st_transform ( a.line, 21036 ) ) :: numeric, 2 ) as length,
3332440,
3331436,
3350003
from tmp as a; 

-- Ndola to Luanshya (abandoned)
with tmp as(
SELECT X.* FROM pgr_dijkstra(
                'SELECT oid as id, source, target, length AS cost FROM zambia_osm_edges',
                3331444,
		3330025,
		false
		) AS X
		ORDER BY seq)
update zambia_osm_edges
set line = 'Ndola - Luanshya',
gauge = '1067',
status = 'abandoned',
mode = 'mixed',
comment = 'Complete reconstruction needed'
where oid in (select edge from tmp);

-- Proposed Chipata - TAZARA link (approved and funded)

INSERT INTO zambia_osm_edges ("geom", "oid" ) VALUES ('0102000020E610000019000000476E7F8E1D524040D7540AA6C8572BC03E868231B35040404A6E3202CC6B2BC03543E55AD74340405BE160194A8D2BC04A285CF6AE364040813906CC9FA12BC055B729257124404094D24C0F91B32BC04C8798E4CE0F4040B8DEC16900E72BC0A5FFD43AE90E4040B220498DC0342CC01BA02503B70D4040D878EE3F16492CC04444FB0DF3024040242939A5C1712CC09DA691796AE13F40AE88E8DCF3722CC09FDFB53B17CA3F40D4E08D8F49872CC0B74981F181863F40E89FECFEAD892CC0A7FC6A0677553F401044C209EA7E2CC0477AB59B2D323F4013B60A8E43502CC05DAB5C8FEB053F407B5575C3ECFE2BC0ACF307A563F03E405E4900697DCB2BC0E86948B53DE03E402432FC46C3B42BC0D5D001724CCE3E4075A0BF88AE8F2BC0EAC884A35DB93E403DAFD39267692BC07661589D3CA33E402B3CA57BE9472BC02878E975E4913E40A79A6E20F7F82AC03D706CA7F57C3E400CC890D146D62AC03E9684D3686D3E405C103CE7BEC02AC0537BFB6E40603E405E5C6C3FA5A12AC0C1E84DA0E34C3E403119D8744E692AC0', 3350004);

with tmp as(
select a.oid, b.oid as source, c.oid as target
from zambia_osm_edges a
join zambia_osm_nodes b on st_intersects(b.geom, st_startpoint(a.geom))
join zambia_osm_nodes c on st_intersects(c.geom, st_endpoint(a.geom))
where a.oid = 3350004
)
update zambia_osm_edges a
set 
	source = b.source,
	target = b.target,
	length = round( st_length ( st_transform ( a.geom, 21036 ) ) :: numeric, 2 ),
	mode = 'mixed',
	status = 'proposed',
	line = 'Chipata-TAZARA',
	gauge = 1067,
	comment = 'Approved and funded'
from tmp b
WHERE a.oid = b.oid;


-- create spatial indexes
CREATE INDEX zambia_osm_edges_geom_idx
  ON zambia_osm_edges
  USING GIST (geom);

CREATE INDEX zambia_osm_nodes_geom_idx
  ON zambia_osm_nodes
  USING GIST (geom);


-- update station gauge on stations

update zambia_osm_nodes
set gauge = '1067'
where st_intersects(geom, (select st_collect(geom) from zambia_osm_edges where gauge = '1067'))
and railway in ('station', 'halt', 'stop');



-- test routing		
		SELECT X.*, a.line, a.status, b.railway, b.name FROM pgr_dijkstra(
                'SELECT oid as id, source, target, length AS cost FROM zambia_osm_edges',
                3330130,
		3330033,
		false
		) AS X left join
		zambia_osm_edges as a on a.oid = X.edge left join
		zambia_osm_nodes as b on b.oid = X.node
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
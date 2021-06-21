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
-- kenya ids start 1110000
UPDATE kenya_osm_edges set source = 1110000 + reverse(split_part(reverse(from_id), '_', 1))::int4;
UPDATE kenya_osm_edges set target = 1110000 + reverse(split_part(reverse(to_id), '_', 1))::int4;
UPDATE kenya_osm_edges set oid = 1110000 + reverse(split_part(reverse(id), '_', 1))::int4;

-- make primary key
ALTER TABLE kenya_osm_edges DROP CONSTRAINT kenya_osm_edges_pkey;
ALTER TABLE kenya_osm_edges ADD PRIMARY KEY (oid);

-- add oid column to nodes
ALTER TABLE kenya_osm_nodes ADD COLUMN oid int4;
UPDATE kenya_osm_nodes set oid = 1110000 + reverse(split_part(reverse(id), '_', 1))::int4;

-- make primary key
ALTER TABLE kenya_osm_nodes DROP CONSTRAINT kenya_osm_nodes_pkey;
ALTER TABLE kenya_osm_nodes ADD PRIMARY KEY (oid);

-- delete duplicate station nodes(on same gauge)
-- Nanyuki
delete from kenya_osm_nodes where oid in (1110246);

alter table kenya_osm_nodes
add COLUMN gauge text,
add COLUMN facility text; -- dry_port, gauge_interchange etc

-- update nodes values

-- set additional node for stations
update kenya_osm_nodes
set name = 'Nairobi Central Station',
railway = 'station'
where oid = 1111699;

update kenya_osm_nodes
set name = 'Makadara Railway Station',
railway = 'station'
where oid = 1111354;

-- incorrect name
-- Jomo Kenyatta International Airport is Embakasi Village (bus available to JKIA from here)
-- different from the proposed airport rail link via Syokimau
update kenya_osm_nodes
set name = 'Embakasi Village'
where oid = 1110094;

-- amend Mombasa station node
UPDATE kenya_osm_nodes
SET name = 'Mombasa Terminus',
railway = 'station'
where oid = 1110956;

UPDATE kenya_osm_nodes
SET name = 'Old Mombasa Station',
railway = 'station'
where oid = 1111512;

-- remove bad station node in middle of nowhere
delete from kenya_osm_nodes where oid = 1110730;

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
 
 -- tunnels
 -- Nachu (1112056)
 -- Ngong (1111598)
 update kenya_osm_edges
 set structure = 'tunnel'
 where oid in (1112056, 1111598)
 
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
-- oid 1111339 -> Taveta
-- oid 1111341 -> Nanyuki
-- oid 1110205 -> Kiganjo
-- oid 1110286 -> Equator
-- oid 1110340 -> Moi's Bridge
-- oid 1110476 -> Webuye
-- otherwise unnamed

update kenya_osm_nodes
set name = 
(case when oid = 1111339 then 'Taveta'
when oid = 1111341 then 'Nanyuki'
when oid = 1110205 then 'Kiganjo'
when oid = 1110286 then 'Equator'
when oid = 1110340 then 'Moi''s Bridge'
when oid = 1110476 then 'Webuye'
else 'unnamed'
end)
where name is null and railway in ('station', 'stop', 'halt');

-- facilities
update kenya_osm_nodes
set name = 'Nairobi Inland Container Port',
facility = 'dry_port',
railway = 'stop'
where oid = 1113126;

update kenya_osm_nodes
set name = 'Kisumu Inland Container Depot',
facility = 'dry_port',
railway = 'stop'
where oid = 1111835;

update kenya_osm_nodes
set name = 'Naivasha Inland Container Depot (SGR)',
facility = 'dry_port',
railway = 'stop'
where oid = 1111259;

update kenya_osm_nodes
set name = 'Naivasha Inland Container Depot (MGR)',
facility = 'dry_port',
railway = 'stop',
gauge = '1000'
where oid = 1113089;

update kenya_osm_nodes
set name = 'Mombasa Port',
facility = 'container_port',
railway = 'stop'
where oid = 1113191;

update kenya_osm_nodes
set name = 'Mombasa Port',
facility = 'container_port',
railway = 'stop'
where oid = 1112489;

-- create new station nodes
-- this is required as there can be several edges running through stations but the station node
-- is located on an edge that isn't used for the route.

-- Kajiado Railway Station 1110437 -> 1111097
-- Kima 1111304 -> 1112071
-- Kibwezi Station 1111350 -> 1111543
-- Tsavo 1110700 -> 1112044
-- Voi Station 1111349 -> 1111477
-- Miasenyi Station 1111348 -> 1111452
-- Mgalani 1110699 -> 1112028
-- Malaba 1110164 -> 1110291
-- Eldoret 1110217 -> 1112419
-- Kipkarren 1110336 -> 1110939

DO $$ DECLARE
-- create new station nodes
-- note: must not be a node coincident with the closest point (reassign that node as a station instead)
nodes INT ARRAY DEFAULT ARRAY [1110437, 1111304, 1111350, 1110700, 1111349, 1111348, 1110699, 1110164, 1110217, 1110336 ];
edges INT ARRAY DEFAULT ARRAY [1111097, 1112071, 1111543, 1112044, 1111477, 1111452, 1112028, 1110291, 1112419, 1110939 ];
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
	tmp2 as ( select geom2 as geom, length, ( oid :: text || row_number ( ) over ( ) ) :: int as oid, line, gauge, status, mode, structure, speed_freight, speed_passenger, comment, st_startpoint ( geom2 ), st_endpoint ( geom2 ) from tmp ) select
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
-- split 1112553 at 1113084
-- split 1112554 at 1112756
-- allow routing from Nairobi Terminus to Naivasha
-- split 1111525 at 1113139
-- allow routing to old Mombasa Station via Tudor Creek
-- split 1110141 at 1111517
-- allow routing of Changamwe-Kilindini freight
-- split 1110236 at 1112497
-- split 1111781 at 1112488
-- allow routing between Eldoret and Malaba
-- split 1110495 at 1113013
-- allow routing between Kisumu and Butere
-- split 1110149 at 1112215
-- allow routing between Gilgil and Nyahururu
-- split 1111166 at 1111826
-- allow routing between Rongai and Solai
-- split  1110179 at 1111691
-- allow routing between Eldoret and Kitale
-- split 1112374 at 1112820
-- allow routing between Makadara and Nanyuki
-- split 1112551 at 1113109
-- allow routing from Nakuru-Kisumu to Chemelil town
-- split 1110519 at 1112159
-- allow routing from Voi to Taveta
-- split 1111289 at 1111978
-- SGR
-- allow routing out of Mombasa Terminus
-- split 1111587 at 1112296
-- split 1111586 at 1112819
-- routing out/in Imara and old Mombasa line
-- split 1112000 at 1112757
-- allow routing into Kisumu Inland Container Depot
-- split 1111661 at 1111834
-- allow routing into Naivasha Inland Container Depot
-- split 1112283 at 1112887


DO $$ DECLARE
 edges INT ARRAY DEFAULT ARRAY [1112553, 1112554, 1111525, 1110141, 1110236, 1111781, 1110495, 1110149, 1111166, 1110179, 1112374, 1112551, 1110519, 1111289, 1111587, 1111586, 1112000, 1111661, 1112283 ];
 nodes INT ARRAY DEFAULT ARRAY [1113084, 1112756, 1113139, 1111517, 1112497, 1112488, 1113013, 1112215, 1111826, 1111691, 1112820, 1113109, 1112159, 1111978, 1112296, 1112819, 1112757, 1111834, 1112887 ];
-- edges INT ARRAY DEFAULT ARRAY [1112283 ];
-- nodes INT ARRAY DEFAULT ARRAY [1112887 ];
edge INT;
node INT;
BEGIN
		for edge, node in select unnest(edges), unnest(nodes)
		LOOP
		raise notice'counter: %', edge || ' ' || node;
	insert into kenya_osm_edges with tmp as (select a.*, (st_dump(st_split(a.geom, b.geom))).geom as geom2 from kenya_osm_edges a, kenya_osm_nodes b where a.oid = edge and b.oid = node),
	tmp2 as (select geom2 as geom, length, ( oid :: text || row_number ( ) over ( ) ) :: int as oid, line, gauge, status, mode, structure, speed_freight, speed_passenger, comment, st_startpoint ( geom2 ), st_endpoint ( geom2 ) from tmp ) select 
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

-- connect the NICD Longonot line to the metre gauge at - add node 1110290  to beginning of line 1112532 (positon zero) and change source to 1110290
UPDATE kenya_osm_edges
	SET geom = ST_AddPoint(geom, (select geom from kenya_osm_nodes where oid = 1110290), 0),
	source = 1110290,
	gauge = '1000',
	line = 'NICD - Longonot Railway Link'
   WHERE oid = 1112532;
-- update
UPDATE kenya_osm_edges
	SET length = round(st_length(st_transform(geom, 32736))::numeric,2)
	WHERE oid = 1112532;

-- gap in edge on Magadi line. Extend line 1111106 to node 1112801
UPDATE kenya_osm_edges
	SET geom = ST_AddPoint(geom, (select geom from kenya_osm_nodes where oid = 1112801), st_npoints(geom)),
	target = 1112801
   WHERE oid = 1111106;
		
-- Update line information
-- metre gauge lines	
		
-- Makadara to Nanyuki

with tmp as(
SELECT X.* FROM pgr_dijkstra(
                'SELECT oid as id, source, target, length AS cost FROM kenya_osm_edges',
                1111354,
		1110246,
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
                1111512,
		1111699,
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
                1111512,
		1110093,
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
                1111517,
		1112489,
		false
		) AS X
		ORDER BY seq)
update kenya_osm_edges
set status = 'disused',
mode = 'freight',
line = 'Changamwe-Kilindini'
where oid in (select edge from tmp);


-- Nakuru to Malaba (border with Uganda) 
with tmp as(
SELECT X.* FROM pgr_dijkstra(
                'SELECT oid as id, source, target, length AS cost FROM kenya_osm_edges',
                1111520,
		1111632,
		false
		) AS X
		ORDER BY seq)
update kenya_osm_edges
set line = 'Nakuru-Malaba',
gauge = '1000',
status = 'rehabilitation',
comment = 'Currently out of use, rehabilitation due to be completed September 2021 (https://bit.ly/2TKPIcN)'
where oid in (select edge from tmp);


-- Nakuru to Kisumu
with tmp as(
SELECT X.* FROM pgr_dijkstra(
                'SELECT oid as id, source, target, length AS cost FROM kenya_osm_edges',
                1111520,
		1110663,
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
                1112215,
		1111792,
		false
		) AS X
		ORDER BY seq)
update kenya_osm_edges
set line = 'Kisumu-Butere',
status = 'disused',
comment = 'May be rehabilitated following recent rehabilitation of Nakuru to Kisumu'
where oid in (select edge from tmp);

-- Rongai to Solai
with tmp as(
SELECT X.* FROM pgr_dijkstra(
                'SELECT oid as id, source, target, length AS cost FROM kenya_osm_edges',
                1111691,
		1111690,
		false
		) AS X
		ORDER BY seq)
update kenya_osm_edges
set line = 'Rongai-Solai',
gauge = '1000'
where oid in (select edge from tmp);


-- Gilgil to Nyahururu
with tmp as(
SELECT X.* FROM pgr_dijkstra(
                'SELECT oid as id, source, target, length AS cost FROM kenya_osm_edges',
                1111826,
		1111829,
		false
		) AS X
		ORDER BY seq)
update kenya_osm_edges
set line = 'Gilgil-Nyahururu',
gauge = '1000'
where oid in (select edge from tmp);


-- Eldoret to Kitale
with tmp as(
SELECT X.* FROM pgr_dijkstra(
                'SELECT oid as id, source, target, length AS cost FROM kenya_osm_edges',
                1112820,
		1112095,
		false
		) AS X
		ORDER BY seq)
update kenya_osm_edges
set line = 'Eldoret-Kitale',
gauge = '1000'
where oid in (select edge from tmp);

	
-- branch to Chemelil town
with tmp as(
SELECT X.* FROM pgr_dijkstra(
                'SELECT oid as id, source, target, length AS cost FROM kenya_osm_edges',
                1112159,
		1112160,
		false
		) AS X
		ORDER BY seq)
update kenya_osm_edges
set line = 'Chemelil branch',
gauge = '1000'
where oid in (select edge from tmp);		

	
-- from Nairobi to Nakuru
with tmp as(
SELECT X.* FROM pgr_dijkstra(
                'SELECT oid as id, source, target, length AS cost FROM kenya_osm_edges',
                1111699,
		1111520,
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
                1111244,
		1112868,
		false
		) AS X
		ORDER BY seq)
update kenya_osm_edges
set line = 'Konza-Magadi',
comment = 'Primarily used by Tata Chemicals, though a commuter route between Kajiado and Konza. See: https://bit.ly/3cPblzg'
where oid in (select edge from tmp);		

		
-- from Voi to Taveta
with tmp as(
SELECT X.* FROM pgr_dijkstra(
                'SELECT oid as id, source, target, length AS cost FROM kenya_osm_edges',
                1111978,
		1111979,
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
                1110956,
		1111228,
		false
		) AS X
		ORDER BY seq)
update kenya_osm_edges
set line = 'Mombasa-Nairobi SGR',
gauge = '1435',
speed_passenger = 120,
speed_freight = 80
where oid in (select edge from tmp);		

-- 	Mombasa-Nairobi SGR freight only
with tmp as(
SELECT X.* FROM pgr_dijkstra(
                'SELECT oid as id, source, target, length AS cost FROM kenya_osm_edges',
                1110956,
		1113191,
		false
		) AS X
		ORDER BY seq)
update kenya_osm_edges
set line = 'Mombasa-Nairobi SGR',
gauge = '1435',
mode = 'freight',
speed_freight = 80
where oid in (select edge from tmp);		

-- also at Nairobi

-- Nairobi-Naivasha (Suswa) SGR
with tmp as(
SELECT X.* FROM pgr_dijkstra(
                'SELECT oid as id, source, target, length AS cost FROM kenya_osm_edges',
                1111228,
		1111229,
		false
		) AS X
		ORDER BY seq)
update kenya_osm_edges
set line = 'Nairobi-Naivasha SGR',
gauge = '1435',
speed_passenger = 120,
speed_freight = 80
where oid in (select edge from tmp);		

-- Naivasha (Suswa) - Kisumu SGR
with tmp as(
SELECT X.* FROM pgr_dijkstra(
                'SELECT oid as id, source, target, length AS cost FROM kenya_osm_edges',
                1111229,
		1110714,
		false
		) AS X
		ORDER BY seq)
update kenya_osm_edges
set line = 'Naivasha-Kisumu SGR',
gauge = '1435',
speed_passenger = 120,
speed_freight = 80
where oid in (select edge from tmp);		

-- Nairobi Terminus to Inland Port - freight only
with tmp as(
SELECT X.* FROM pgr_dijkstra(
                'SELECT oid as id, source, target, length AS cost FROM kenya_osm_edges',
                1112845,
		1113126,
		false
		) AS X
		ORDER BY seq)
update kenya_osm_edges
set line = 'Nairobi Terminus-Inland Container Port Nairobi SGR',
gauge = '1435',
mode = 'freight',
speed_freight = 80
where oid in (select edge from tmp);		

-- Kibos - Kisumu Inland Container Port
with tmp as(
SELECT X.* FROM pgr_dijkstra(
                'SELECT oid as id, source, target, length AS cost FROM kenya_osm_edges',
                1111834,
		1111835,
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
                1112887,
		1111259,
		false
		) AS X
		ORDER BY seq)
update kenya_osm_edges
set line = 'Naivasha Inland Container Port',
gauge = '1435',
mode = 'freight',
status = 'open',
speed_freight = 80
where oid in (select edge from tmp);

-- add edge for NICD gauge interchange. Assume 24 hour cost.
with tmp as
(
select st_makeline(a.geom, b.geom) as line from kenya_osm_nodes a, kenya_osm_nodes b where a.oid = 1113089 and b.oid = 1111259
)
insert into kenya_osm_edges select 
a.line,
round( st_length ( st_transform ( a.line, 21036 ) ) :: numeric, 2 ) as length,
1113089,
1111259,
1130000
from tmp as a;

update kenya_osm_edges
set gauge = '1000 <-> 1435',
mode = 'freight',
status = 'construction',
line = 'NICD gauge interchange'
where oid = 1130000;

-- Embakasi Village - Nairobi
with tmp as(
SELECT X.* FROM pgr_dijkstra(
                'SELECT oid as id, source, target, length AS cost FROM kenya_osm_edges',
                1111480,
		1112849,
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
                1111330,
		1112757,
		false
		) AS X
		ORDER BY seq)
update kenya_osm_edges
set line = 'Syokimau',
gauge = '1000',
status = 'open'
where oid in (select edge from tmp);

-- create spatial indexes
CREATE INDEX kenya_osm_edges_geom_idx
  ON kenya_osm_edges
  USING GIST (geom);

CREATE INDEX kenya_osm_nodes_geom_idx
  ON kenya_osm_nodes
  USING GIST (geom);

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
                1110059,
		1110663,
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
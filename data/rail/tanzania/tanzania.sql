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
		ADD COLUMN status text, -- open, abandoned, disused, rehabilitation, construction, proposed
		ADD COLUMN mode text, -- passenger, freight or mixed.
		ADD COLUMN structure text, -- bridges etc
		ADD COLUMN speed_freight integer,
		ADD COLUMN speed_passenger integer,
		ADD COLUMN comment text;
		
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
-- see: https://www.thecitizen.co.tz/tanzania/news/trc-shifts-main-station-to-kamata-temporarily--2653910
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
set name = 'Dar es Salaam',
railway = 'station'
where oid = 1971;

-- SGR stations
update tanzania_osm_nodes
set name = 'Morogoro SGR'
where oid = 1959;

update tanzania_osm_nodes
set name = 'Pugu SGR',
railway = 'station'
where oid = 1960;

update tanzania_osm_nodes
set name = 'Dar es Salaam SGR',
railway = 'station'
where oid = 3888;

--other stations 
update tanzania_osm_nodes
set name = 'Dar es Salaam',
railway = 'station'
where oid = 2785;


-- incorrect name
-- Kamata station node incorrectly on SGR line
update tanzania_osm_nodes
set name = NULL,
railway = NULL
where oid = 29;


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
-- Kamata station node is incorrectly on the new SGR node 29 to 3193
-- Puga SGR node 1960 to 3156
-- Ndui station 392 to 1912
-- Mwanza South 333 to 1226
-- Fella 712 to 1285
-- Bukene 721 to 246
-- Makutopora 797 to 3280
-- Morogoro 312 - 830
DO $$ DECLARE
-- create new station nodes
-- note: must not be a node coincident with the closest point (reassign that node as a station instead)
-- nodes INT ARRAY DEFAULT ARRAY [326,  478,  29,   1960,  392,  333,  712, 721,  797, 312];
-- edges INT ARRAY DEFAULT ARRAY [2583, 1871, 3193, 3156, 1912, 1226, 1285, 246, 3280, 830];
nodes INT ARRAY DEFAULT ARRAY [392,  333,  712, 721,  797, 312];
edges INT ARRAY DEFAULT ARRAY [1912, 1226, 1285, 246, 3280, 830];
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

-- allow routing from Moshi to Arusha
-- split 2291 at 2709

-- allow routing into Arusha station
-- split 652 at 3612

DO $$ DECLARE
-- edges INT ARRAY DEFAULT ARRAY [2850, 137,  3518, 850,  2291, 652,];
-- nodes INT ARRAY DEFAULT ARRAY [2601, 2901, 3287, 2585, 2709, 3612];
edges INT ARRAY DEFAULT ARRAY [652];
nodes INT ARRAY DEFAULT ARRAY [3612];
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
	a.structure,
	a.speed_freight,
	a.speed_passenger 
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
set line = 'Central Line',
gauge = '1000',
status = 'open',
speed_freight = 30,
comment = 'Rehabilitation project underway. Due to complete 30 September 2022'
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
set line = 'Central Line',
gauge = '1000',
status = 'open',
mode = 'freight',
speed_freight = 30,
comment = 'Rehabilitation project underway. Due to complete 30 September 2022'
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
set line = 'Mpanda Line',
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
set line = 'Mwanza Line',
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
set line = 'Singida Line',
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

-- Kidatu Line Kilosa-Msolwa (disused)
with tmp as(
SELECT X.* FROM pgr_dijkstra(
                'SELECT oid as id, source, target, length AS cost FROM tanzania_osm_edges',
                2901,
		3212,
		false
		) AS X
		ORDER BY seq)
update tanzania_osm_edges
set line = 'Kidatu Line',
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

-- Tanga Line to Moshi
with tmp as(
SELECT X.* FROM pgr_dijkstra(
                'SELECT oid as id, source, target, length AS cost FROM tanzania_osm_edges',
                1954,
		116,
		false
		) AS X
		ORDER BY seq)
update tanzania_osm_edges
set line = 'Tanga Line (to Moshi)',
gauge = '1000',
status = 'open'
where oid in (select edge from tmp);

-- Tanga Line Moshi to Arusha
with tmp as(
SELECT X.* FROM pgr_dijkstra(
                'SELECT oid as id, source, target, length AS cost FROM tanzania_osm_edges',
                2709,
		112,
		false
		) AS X
		ORDER BY seq)
update tanzania_osm_edges
set line = 'Tanga Line (Moshi-Arusha)',
gauge = '1000',
status = 'open'
where oid in (select edge from tmp);

-- disused commuter rail branch to Ubungo Maziwa
with tmp as(
SELECT X.* FROM pgr_dijkstra(
                'SELECT oid as id, source, target, length AS cost FROM tanzania_osm_edges',
                1982,
		3660,
		false
		) AS X
		ORDER BY seq)
update tanzania_osm_edges
set line = 'TRL Commuter Rail (Ubungu Branch)',
gauge = '1000',
status = 'disused'
where oid in (select edge from tmp);

-- 1000mm gauge to Dar es Salaam International Container port
with tmp as(
SELECT X.* FROM pgr_dijkstra(
                'SELECT oid as id, source, target, length AS cost FROM tanzania_osm_edges',
                2785,
		2188,
		false
		) AS X
		ORDER BY seq)
update tanzania_osm_edges
set line = 'International Container Terminal (metre gauge)',
gauge = '1000',
status = 'open',
mode = 'freight'
where oid in (select edge from tmp);

-- simplify network - add line to link Yombo to Kurasini (Commuter rail and freight to container terminal)
with tmp as
(
select st_makeline(a.geom, b.geom) as line from tanzania_osm_nodes a, tanzania_osm_nodes b where a.oid = 425 and b.oid = 2124
)
insert into tanzania_osm_edges select 
a.line,
round( st_length ( st_transform ( a.line, 21036 ) ) :: numeric, 2 ) as length,
425,
2124,
999910000
from tmp as a

-- 1067 mm gauge (Tazara) to Kurasini / Conatiner Terminal 


-- TAZARA Line (to Tazmanian border with Zambia)
with tmp as(
SELECT X.* FROM pgr_dijkstra(
                'SELECT oid as id, source, target, length AS cost FROM tanzania_osm_edges',
                1971,
		2271,
		false
		) AS X
		ORDER BY seq)
update tanzania_osm_edges
set line = 'TAZARA (Tanzania)',
gauge = '1067',
status = 'open',
mode = 'mixed'
where oid in (select edge from tmp);

-- Dar es Salaam - Morogoro SGR 
with tmp as(
SELECT X.* FROM pgr_dijkstra(
                'SELECT oid as id, source, target, length AS cost FROM tanzania_osm_edges',
                3888,
		1959,
		false
		) AS X
		ORDER BY seq)
update tanzania_osm_edges
set line = 'Dar es Salaam - Morogoro SGR',
gauge = '1435',
status = 'construction',
mode = 'mixed',
comment = 'Phase 1 - testing to start in 2021',
speed_freight = 120,
speed_passenger = 160
where oid in (select edge from tmp);

-- Morogoro - Makutupora SGR 
with tmp as(
SELECT X.* FROM pgr_dijkstra(
                'SELECT oid as id, source, target, length AS cost FROM tanzania_osm_edges',
                1959,
		3857,
		false
		) AS X
		ORDER BY seq)
update tanzania_osm_edges
set line = 'Morogoro - Makutupora SGR',
gauge = '1435',
status = 'construction',
mode = 'mixed',
comment = 'Phase 2 - due for completion February 2022',
speed_freight = 120,
speed_passenger = 160
where oid in (select edge from tmp);


update tanzania_osm_nodes
set gauge = 'metre'
where st_intersects(geom, (select st_collect(geom) from tanzania_osm_edges where gauge = 'metre'))
and railway in ('station', 'halt', 'stop');

update tanzania_osm_nodes
set gauge = 'standard'
where st_intersects(geom, (select st_collect(geom) from tanzania_osm_edges where gauge = 'standard'))
and railway in ('station', 'halt', 'stop');


-- Mtwara - Mbamba Bay etc
-- proposed line
-- digitised in QGIS
-- oids start with 888######
-- edges
INSERT INTO tanzania_osm_edges ("geom", "oid") VALUES ('0102000020E61000001000000010A79810AF1A4440C049B295668E24C0250D5D845A1A44405840ECA8749024C0F84BC4469C1A44406CE86B59AF9324C09EC992CB1F1B44402BF8D93A3C9824C0FB40D49C031B4440C3EE134E4A9A24C012023758CB0E444074C1B02E29B824C06A24C50E4FF743400192FA85959224C02DBEAFD7B1E54340A09C2D684F6824C0EF579AA014D443406AEE71C7667624C08E7DB253DCCB434050E149D5563924C02C88E53596A143406287C7A3DBBC24C02C88E53596A143406287C7A3DBBC24C0350A752A2F7D43406B5A060B9EFE24C0350A752A2F7D43406B5A060B9EFE24C0EF06EB2DEB6D434062F35BE7124525C0127BBD4386644340B2AE3F7A0B7425C0', 888000001),
('0102000020E610000009000000127BBD4386644340B2AE3F7A0B7425C06100D734634F4340A947955680BA25C0C2BFD9B08D3543401C774BFF13E025C0C2BFD9B08D3543401C774BFF13E025C09693AD043E1F4340625FF02A4ACD25C000F024460F0343402EB1348A61DB25C0359EE0E6F7F44240E7C88F5E2BEE25C0F71CE6DE4CC142402EB1348A61DB25C03E058B0A83AE42405AF84507BF1326C0', 888000002),
('0102000020E6100000100000003E058B0A83AE42405AF84507BF1326C073B346AB6BA04240D68EA6D3DDF225C0093CEA988C9A4240DEF550F768AC25C0CBD5D461EF8842405A8CB1C3878B25C0C21D7BCB3A69424024DEF5229F9925C07B1AF1CEF659424013A40C98519E25C07B1AF1CEF659424013A40C98519E25C04FEEC422A74342405A8CB1C3878B25C072629738423A424050B9725CC54925C072629738423A424050B9725CC54925C03E99F6C64B264240DE89BCB3312425C008D0555555124240247261DF671125C0461B86BBE4014240BA15EA9D962D25C01152E549EEED4140A9DB0013493225C01152E549EEED4140A9DB0013493225C0E525B99D9ED74140F896E4A5416125C0', 888000003),
('0102000020E610000008000000E525B99D9ED74140F896E4A5416125C034ABD28E7BC24140C4E82805596F25C03D2D6283149E41408E3A6D64707D25C08DB27B74F1884140DEF550F768AC25C08DB27B74F1884140DEF550F768AC25C0D39A20A027764140BBED1225053E26C058E9DA02FB744140D6FA3A17157B26C0753CC2D9D0664140CE869E83709026C0', 888000004),
('0102000020E610000005000000E525B99D9ED74140F896E4A5416125C0A7BFA36601C6414001FE8EC9CC1A25C046E5BB19C9BD4140DE1D2870FA9B24C046E5BB19C9BD4140DE1D2870FA9B24C0E50AD4CC90B54140B2D616F39C6324C0', 888000005),
('0102000020E610000003000000E50AD4CC90B54140B2D616F39C6324C09E074AD04CA641400AF9A4A9204C24C05804C0D3089741403EA7604A093E24C0', 888000006),
('0102000020E6100000050000005804C0D3089741403EA7604A093E24C0233B1F6212834140487A9FB1CB7F24C072C03853EF6D4140DE1D2870FA9B24C0B00B69B97E5D4140CCE33EE5ACA024C0E5B9245A674F4140DE1D2870FA9B24C0', 888000007),
('0102000020E6100000020000005804C0D3089741403EA7604A093E24C088E9013EBE7C4140669649CEFBD423C0', 888000008);

-- nodes
INSERT INTO tanzania_osm_nodes ("geom" , "oid") VALUES ('0101000020E61000003E058B0A83AE42405AF84507BF1326C0', 888000001),
('0101000020E6100000E525B99D9ED74140F896E4A5416125C0', 888000002),
('0101000020E6100000753CC2D9D0664140CE869E83709026C0', 888000003),
('0101000020E6100000E50AD4CC90B54140B2D616F39C6324C0', 888000004),
('0101000020E61000005804C0D3089741403EA7604A093E24C0', 888000005),
('0101000020E6100000E5B9245A674F4140DE1D2870FA9B24C0', 888000006),
('0101000020E610000010A79810AF1A4440C049B295668E24C0', 888000007),
('0101000020E610000088E9013EBE7C4140669649CEFBD423C0', 888000008),
('0101000020E6100000127BBD4386644340B2AE3F7A0B7425C0', 888000009);

-- need to populate source, target and length
-- get nodes coincident with start and end of line

with tmp as(
select a.oid, b.oid as source, c.oid as target
from tanzania_osm_edges a
join tanzania_osm_nodes b on st_intersects(b.geom, st_startpoint(a.geom))
join tanzania_osm_nodes c on st_intersects(c.geom, st_endpoint(a.geom))
where a.oid > 888000000 and a.oid < 999000000
)
update tanzania_osm_edges a
set 
	source = b.source,
	target = b.target,
	length = round( st_length ( st_transform ( a.geom, 21036 ) ) :: numeric, 2 ),
	mode = 'freight',
	status = 'proposed',
	line = 'Mtwara',
	gauge = 1435,
	comment = 'As of October 2020 feasibility studies and architectural designs have been completed'
from tmp b
WHERE a.oid = b.oid;

-- station nodes
update tanzania_osm_nodes
set railway = 'station',
name = 'Mtwara'
where oid = 888000007;

update tanzania_osm_nodes
set railway = 'station',
name = 'Mbamba Bay'
where oid = 888000003;

update tanzania_osm_nodes
set railway = 'station',
name = 'Liganga mine'
where oid = 888000008;

update tanzania_osm_nodes
set railway = 'station',
name = 'Mchuchuma mine'
where oid = 888000006;

		
-- test routing		
		SELECT X.*, a.line, a.status, b.railway, b.name FROM pgr_dijkstra(
                'SELECT oid as id, source, target, length AS cost FROM tanzania_osm_edges',
                472,
		522,
		false
		) AS X left join
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
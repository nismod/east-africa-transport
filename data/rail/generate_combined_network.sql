-- HVT generated combined routable rail network for Kenya, Tanzania, Zambia, and Uganda

create table hvt_rail_network as
(
select oid, 'kenya' as country, source, target, length, line, status, gauge, mode, structure, speed_freight, speed_passenger, comment, geom
from kenya_osm_edges where line is not null
UNION
select oid, 'tanzania' as country, source, target, length, line, status, gauge, mode, structure, speed_freight, speed_passenger, comment, geom
from tanzania_osm_edges where line is not null
UNION
select oid, 'zambia' as country, source, target, length, line, status, gauge, mode, structure, speed_freight, speed_passenger, comment, geom
from zambia_osm_edges where line is not null
UNION
select oid, 'uganda' as country, source, target, length, line, status, gauge, mode, structure, speed_freight, speed_passenger, comment, geom
from uganda_osm_edges where line is not null
order by country, line asc
);

ALTER TABLE hvt_rail_network ADD PRIMARY KEY (oid);

-- nodes table is just stations/stops/halts coincident with edges in respective networks
create table hvt_rail_nodes as
(
select distinct a.oid, 'kenya' as country, a.railway, a.name, a.facility, a.gauge, a.geom from kenya_osm_nodes a
JOIN kenya_osm_edges b ON st_intersects(a.geom, b.geom)
where a.railway in ('station', 'halt', 'stop') and b.line is not null
UNION
select distinct a.oid, 'tanzania' as country, a.railway, a.name, a.facility, a.gauge, a.geom from tanzania_osm_nodes a
JOIN tanzania_osm_edges b ON st_intersects(a.geom, b.geom)
where a.railway in ('station', 'halt', 'stop') and b.line is not null
UNION
select distinct a.oid, 'zambia' as country, a.railway, a.name, a.facility, a.gauge, a.geom from zambia_osm_nodes a
JOIN zambia_osm_edges b ON st_intersects(a.geom, b.geom)
where a.railway in ('station', 'halt', 'stop') and b.line is not null
UNION
select distinct a.oid, 'uganda' as country, a.railway, a.name, a.facility, a.gauge, a.geom from uganda_osm_nodes a
JOIN uganda_osm_edges b ON st_intersects(a.geom, b.geom)
where a.railway in ('station', 'halt', 'stop') and b.line is not null
order by country, name asc
);

ALTER TABLE hvt_rail_nodes ADD PRIMARY KEY (oid);

-- make connections between countries

-- Tanzania <-> Zambia (TAZARA)
-- change target of edge 2220923 to 3331236

update hvt_rail_network
set target = 3331236
where oid = 2220923;

-- Kenya <-> Tanzania via Taveta
-- disused line currently
update hvt_rail_network
set source = 2222705
where oid = 1110976;

-- Kenya <-> Uganda
-- old Uganda line
-- change source on 1110290 to 4440911
update hvt_rail_network
set source = 4440911
where oid = 1110290;

-- test routing		

-- Dar es Salaam (Tanzania) to New Kapiri Mposhi (Zambia) (TAZARA)
		SELECT X.*, a.country, a.line, a.gauge, a.status, b.railway, b.name FROM pgr_dijkstra(
                'SELECT oid as id, source, target, length AS cost FROM hvt_rail_network',
                2221971,
		3330084,
		false
		) AS X left join
		hvt_rail_network as a on a.oid = X.edge left join
		hvt_rail_nodes as b on b.oid = X.node
		ORDER BY seq;
		
-- Old Mobassa (Kenya) to Dar es Salaam (Tanzania) via metre gauge (assuming was all in use)
		SELECT X.*, a.country, a.line, a.gauge, a.status, b.railway, b.name FROM pgr_dijkstra(
                'SELECT oid as id, source, target, length AS cost FROM hvt_rail_network',
                1111512,
		2222785,
		false
		) AS X left join
		hvt_rail_network as a on a.oid = X.edge left join
		hvt_rail_nodes as b on b.oid = X.node
		ORDER BY seq;
		
-- Old Mobassa (Kenya) to Kampala (Uganda)
		SELECT X.*, a.country, a.line, a.gauge, a.status, b.railway, b.name FROM pgr_dijkstra(
                'SELECT oid as id, source, target, length AS cost FROM hvt_rail_network',
                1111512,
		4441152,
		false
		) AS X left join
		hvt_rail_network as a on a.oid = X.edge left join
		hvt_rail_nodes as b on b.oid = X.node
		ORDER BY seq;
		
	-- Kampala (Uganda) to Dar es Salaam (Tanzania)
		SELECT X.*, a.country, a.line, a.gauge, a.status, b.railway, b.name FROM pgr_dijkstra(
                'SELECT oid as id, source, target, length AS cost FROM hvt_rail_network',
                4441152,
		2222785,
		false
		) AS X left join
		hvt_rail_network as a on a.oid = X.edge left join
		hvt_rail_nodes as b on b.oid = X.node
		ORDER BY seq;
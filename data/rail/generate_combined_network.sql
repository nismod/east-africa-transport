-- HVT generated combined routable rail network for Kenya, Tanzania, Zambia, and Uganda

create table hvt_rail_network as
(
select oid, 'kenya' as country, source, target, length, line, status, gauge, mode, structure, speed_freight, speed_passenger, NULL::int as time_freight, comment, geom
from kenya_osm_edges where line is not null
UNION
select oid, 'tanzania' as country, source, target, length, line, status, gauge, mode, structure, speed_freight, speed_passenger, NULL::int as time_freight, comment, geom
from tanzania_osm_edges where line is not null
UNION
select oid, 'zambia' as country, source, target, length, line, status, gauge, mode, structure, speed_freight, speed_passenger, NULL::int as time_freight, comment, geom
from zambia_osm_edges where line is not null
UNION
select oid, 'uganda' as country, source, target, length, line, status, gauge, mode, structure, speed_freight, speed_passenger, NULL::int as time_freight, comment, geom
from uganda_osm_edges where line is not null
order by country, line asc
);

ALTER TABLE hvt_rail_network ADD PRIMARY KEY (oid);

-- nodes table is just stations/stops/halts coincident with edges in respective networks
create table hvt_rail_nodes as
(
select distinct a.oid, 'kenya' as country, a.railway as type, a.name, a.facility, a.gauge, a.geom from kenya_osm_nodes a
JOIN kenya_osm_edges b ON st_intersects(a.geom, b.geom)
where a.railway in ('station', 'halt', 'stop') and b.line is not null
UNION
select distinct a.oid, 'tanzania' as country, a.railway as type, a.name, a.facility, a.gauge, a.geom from tanzania_osm_nodes a
JOIN tanzania_osm_edges b ON st_intersects(a.geom, b.geom)
where a.railway in ('station', 'halt', 'stop') and b.line is not null
UNION
select distinct a.oid, 'zambia' as country, a.railway as type, a.name, a.facility, a.gauge, a.geom from zambia_osm_nodes a
JOIN zambia_osm_edges b ON st_intersects(a.geom, b.geom)
where a.railway in ('station', 'halt', 'stop') and b.line is not null
UNION
select distinct a.oid, 'uganda' as country, a.railway as type, a.name, a.facility, a.gauge, a.geom from uganda_osm_nodes a
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


-- freight time costs
-- for SGR based on design speeds
-- for metre gauge based on World Food Programme travel time matrices

-- do a loop for this

-- Nairobi -> Limuru 4 hours
-- Limuru -> Naivasha 4 hours
-- Naivasha -> Nakuru 4 hours
-- Nakuru -> Timboroa 24 hours
-- Timoroa -> Eldoret 4 hours
-- Eldoret -> Bungoma 20 hours
-- Bungoma -> Malaba 8 hours

select name, oid from hvt_rail_nodes where type = 'station' and name like '%Limuru%'

with tmp as(
SELECT a.seq, a.edge, b.length, a.cost, round(((4 * 60) / sum(cost) over () * b.length)::numeric, 2) as time_cost_mins FROM pgr_dijkstra(
                'SELECT oid as id, source, target, length AS cost FROM hvt_rail_network',
                1111699,
		1110169,
		false
		) AS a
		left join
		hvt_rail_network as b on a.edge = b.oid
    ORDER BY seq
		)
update hvt_rail_network a
set time_freight = time_cost_mins
from tmp b
where a.oid = b.edge



UPDATE data.wales
SET destatcocode = naptan.atcocode
FROM data.naptan
WHERE data.wales.deststationlong = data.naptan.stationnam

SELECT region
     , round(sum(suminsured), 2) AS suminsured
     , round((sum(suminsured) * 100) / sum(sum(suminsured)) OVER (), 2) AS pct 
FROM  "Exposure_commune"
GROUP  BY 1;

-- test routing		

-- Dar es Salaam (Tanzania) to New Kapiri Mposhi (Zambia) (TAZARA)
		SELECT X.*, a.country, a.line, a.gauge, a.status, b.type, b.name FROM pgr_dijkstra(
                'SELECT oid as id, source, target, length AS cost FROM hvt_rail_network',
                2221971,
		3330084,
		false
		) AS X left join
		hvt_rail_network as a on a.oid = X.edge left join
		hvt_rail_nodes as b on b.oid = X.node
		ORDER BY seq;
		
-- Old Mobassa (Kenya) to Dar es Salaam (Tanzania) via metre gauge (assuming was all in use)
		SELECT X.*, a.country, a.line, a.gauge, a.status, b.type, b.name FROM pgr_dijkstra(
                'SELECT oid as id, source, target, length AS cost FROM hvt_rail_network',
                1111512,
		2222785,
		false
		) AS X left join
		hvt_rail_network as a on a.oid = X.edge left join
		hvt_rail_nodes as b on b.oid = X.node
		ORDER BY seq;
		
-- Old Mobassa (Kenya) to Kampala (Uganda)
		SELECT X.*, a.country, a.line, a.gauge, a.status, b.type, b.name FROM pgr_dijkstra(
                'SELECT oid as id, source, target, length AS cost FROM hvt_rail_network',
                1111512,
		4441152,
		false
		) AS X left join
		hvt_rail_network as a on a.oid = X.edge left join
		hvt_rail_nodes as b on b.oid = X.node
		ORDER BY seq;
		
	-- Kampala (Uganda) to Dar es Salaam (Tanzania)
		SELECT X.*, a.country, a.line, a.gauge, a.status, b.type, b.name FROM pgr_dijkstra(
                'SELECT oid as id, source, target, length AS cost FROM hvt_rail_network',
                4441152,
		2222785,
		false
		) AS X left join
		hvt_rail_network as a on a.oid = X.edge left join
		hvt_rail_nodes as b on b.oid = X.node
		ORDER BY seq;
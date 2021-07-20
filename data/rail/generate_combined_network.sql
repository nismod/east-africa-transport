-- HVT generated combined routable rail network for Kenya, Tanzania, Zambia, and Uganda

create table hvt_rail_network as
(
select oid, 'kenya' as country, source, target, length, line, status, gauge, mode, structure, speed_freight, speed_passenger, 99999::float4 as time_freight, comment, geom
from kenya_osm_edges where line is not null
UNION
select oid, 'tanzania' as country, source, target, length, line, status, gauge, mode, structure, speed_freight, speed_passenger, 99999::float4 as time_freight, comment, geom
from tanzania_osm_edges where line is not null
UNION
select oid, 'zambia' as country, source, target, length, line, status, gauge, mode, structure, speed_freight, speed_passenger,99999::float4 as time_freight, comment, geom
from zambia_osm_edges where line is not null
UNION
select oid, 'uganda' as country, source, target, length, line, status, gauge, mode, structure, speed_freight, speed_passenger, 99999::float4 as time_freight, comment, geom
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

-- update hvt_rail_network set time_freight = 99999

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

-- Kenya
-- from Old Mombasa to Malaba (metre gauge) - partly disused
-- Old Mombasa 1111512 -> Mariakani 1110440 2 hours
-- Mariakani 1110440 -> Maungu 1110050 4 hours
-- Maungu 1110050 -> VOI 1110360 2 hours
-- Voi 1110360 to Mtito Andei 1110184 5 hours
-- Mtito Andei 1110184 -> Makindu 1110352 3 hours
-- Makindu 1110352 -> Sultan Hamud 1110347 4 hours
-- Sultan Hamud 1110347 -> Nairobi 1111699 4 hours
-- Nairobi 1111699 -> Limuru 1110169 4 hours
-- Limuru 1110169 -> Naivasha 1110295 4 hours
-- Naivasha 1110295 -> Nakuru 1110059 4 hours
-- Nakuru 1110059 -> Timboroa 1110165 24 hours
-- Timboroa 1110165 -> Eldoret 1120217 4 hours
-- Eldoret 1120217 -> Bungoma 1110586 20 hours
-- Bungoma 1110586 -> Malaba 1120164 8 hours

-- Makadara (points) 1112756 -> Nanyuki 1111341
-- Use passenger timetable:
-- http://www.krc.co.ke/wp-content/uploads/2020/12/Nairobi-to-Nanyuki-Train-Fares-and-Schedule.pdf
-- Journey time: 7.5 hours

-- Nakuru (points) 1111520 -> Kisumu 1110663
-- when passenger services were running said to take around 9 hours
-- see: https://www.seat61.com/Kenya.htm#Nairobi%20to%20Kisumu%20by%20train

-- SGR
-- design operating speed for freight: 80kmh = 80/60 km/minute = (80*1000)/60 m/minute

update hvt_rail_network set time_freight = length/((80*1000)/60)
where speed_freight = 80;

-- Longonot gauge interchange. Assume 24 hour time cost
update hvt_rail_network
set time_freight = 1440
where oid = 1130000;

DO $$ DECLARE

origin_nodes INT ARRAY DEFAULT ARRAY [1111512, 1110440, 1110050, 1110360, 1110184, 1110352, 1110347, 1111699, 1110169, 1110295, 1110059, 1110165, 1120217, 1110586, 1112756, 1111520];
destn_nodes  INT ARRAY DEFAULT ARRAY [1110440, 1110050, 1110360, 1110184, 1110352, 1110347, 1111699, 1110169, 1110295, 1110059, 1110165, 1120217, 1110586, 1120164, 1111341, 1110663];
times    FLOAT4 ARRAY DEFAULT ARRAY [2, 4, 2, 5, 3, 4, 4, 4, 4, 4, 24, 4, 20, 8, 7.5, 9];
origin_node  INT; 
destn_node   INT;
time         NUMERIC;

BEGIN
		for origin_node, destn_node, time in select unnest(origin_nodes), unnest(destn_nodes), unnest(times)
		LOOP

raise notice 'counter: %', origin_node || ' ' || destn_node || ' ' || time ;	

with tmp as(
SELECT a.seq, a.edge, b.length, a.cost, round(((time * 60) / sum(cost) over () * b.length)::numeric, 2) as time_cost_mins FROM pgr_dijkstra(
                'SELECT oid as id, source, target, length AS cost FROM hvt_rail_network',
                origin_node,
		destn_node,
		false
		) AS a
		left join
		hvt_rail_network as b on a.edge = b.oid
    ORDER BY seq
		)
update hvt_rail_network a
set time_freight = time_cost_mins
from tmp b
where a.oid = b.edge;

END LOOP;
END $$;

-- Tanzania
-- Central Line

-- Dar es Salaam 2222785 -> Morogoro 2230312 8 hours
-- 2230312 Morogoro -> Dodoma 2220114 8 hours
-- Dodoma 2220114 -> Tabora 2230326 13 hours
-- Tabora 2230326 -> Kigoma 2220563 12 hours

-- Mwanza Line
-- Tabora 2230326 -> Mwanza 2220205 11 hours

-- Tanga Line
-- Tanga to Dar es Salaam is 15 hours
-- Tanga to Morogoro is 15 hours
-- As Dar es Salaam to Morogoro is 8 hours, therefore assume that Tanga to junction between the link line
-- and the central line is 11 hours (15 - 4)
-- Tanga 2221954 -> Junction b/w Link line and Cental Line 2222585 11 hours

-- Tazara Line (Tanzania & Zambia)
-- In 2017 said to take 4 days for freight trains to complete the route (www.railjournal.com/in_depth/new-management-team-aims-to-revitalise-tazara)
-- Dare es Salaam (Tazara) 2221971 -> New Kapiri Mposhi 3330084 96 hours

-- Mpanda line
-- 2017 timetable suggests Kaliwa 2220048 -> Mpanda 2220462 takes 9 hours
-- https://www.fahrplancenter.com/TRL_FAHRPLAN.html

-- Singida Line
-- 2017 timetable suggests Manyoni (points) 2222901 -> Singida 2220317 take 4 hours 
-- https://www.fahrplancenter.com/TRL_FAHRPLAN.html

-- Tanga Line
-- TRC timetable has journey from Korogwe to Arusha taking just over 12 hours. The distance is approx 354km. Suggesting average speed
-- of approx 30kmph. Assume this for the Tanga -> Arusha line

update hvt_rail_network set time_freight = length/((30*1000)/60)
where line like '%Tanga Line%';

-- new SGR will operate at 120 kmph for freight
update hvt_rail_network set time_freight = length/((120*1000)/60)
where speed_freight = 120;

-- assume proposed standard gauge Mtwara line would also operate at 120kmph
update hvt_rail_network set time_freight = length/((120*1000)/60)
where line = 'Mtwara';

-- assume there would be a 24 time cost at Kidatu gauge interchange (currently disused)
update hvt_rail_network
set time_freight = 1440
where oid = 2240010;

DO $$ DECLARE

origin_nodes INT ARRAY DEFAULT ARRAY [2222785, 2230312, 2220114, 2230326, 2230326, 2221954, 2221971, 2220048, 2222901];
destn_nodes  INT ARRAY DEFAULT ARRAY [2230312, 2220114, 2230326, 2220563, 2220205, 2222585, 3330084, 2220462, 2220317];
times    FLOAT4 ARRAY DEFAULT ARRAY [8, 8, 13, 12, 11, 11, 96, 9, 4];
origin_node  INT; 
destn_node   INT;
time         NUMERIC;

BEGIN
		for origin_node, destn_node, time in select unnest(origin_nodes), unnest(destn_nodes), unnest(times)
		LOOP

raise notice 'counter: %', origin_node || ' ' || destn_node || ' ' || time ;	

with tmp as(
SELECT a.seq, a.edge, b.length, a.cost, round(((time * 60) / sum(cost) over () * b.length)::numeric, 2) as time_cost_mins FROM pgr_dijkstra(
                'SELECT oid as id, source, target, length AS cost FROM hvt_rail_network',
                origin_node,
		destn_node,
		false
		) AS a
		left join
		hvt_rail_network as b on a.edge = b.oid
    ORDER BY seq
		)
update hvt_rail_network a
set time_freight = time_cost_mins
from tmp b
where a.oid = b.edge;

END LOOP;
END $$;

-- Zambia

-- New Kapiri Mposhi 3330084 -> junction with Zambia Railways network; south 3331239; north 3331256
-- assume 0

-- Lusaka 3330106 -> Kafue 3330116 1
-- Kafue 3330116 -> Choma 3330130 10
-- Lusaka 3330106 -> Kabwe 3330011 8
-- Kabwe 3330011 -> Ndola 3330010 11
-- Ndola 3330010 -> Kitwe 3330033 3

DO $$ DECLARE

origin_nodes INT ARRAY DEFAULT ARRAY [3330084, 3330084, 3330106, 3330116, 3330106, 3330011, 3330010];
destn_nodes  INT ARRAY DEFAULT ARRAY [3331239, 3331256, 3330116, 3330130, 3330011, 3330010, 3330033];
times    FLOAT4 ARRAY DEFAULT ARRAY [0, 0, 1, 10, 8, 11, 3];
origin_node  INT; 
destn_node   INT;
time         NUMERIC;

BEGIN
		for origin_node, destn_node, time in select unnest(origin_nodes), unnest(destn_nodes), unnest(times)
		LOOP

raise notice 'counter: %', origin_node || ' ' || destn_node || ' ' || time ;	

with tmp as(
SELECT a.seq, a.edge, b.length, a.cost, round(((time * 60) / sum(cost) over () * b.length)::numeric, 2) as time_cost_mins FROM pgr_dijkstra(
                'SELECT oid as id, source, target, length AS cost FROM hvt_rail_network',
                origin_node,
		destn_node,
		false
		) AS a
		left join
		hvt_rail_network as b on a.edge = b.oid
    ORDER BY seq
		)
update hvt_rail_network a
set time_freight = time_cost_mins
from tmp b
where a.oid = b.edge;

END LOOP;
END $$;

-- Uganda
-- no specific information available.

-- all countries
-- all edges with no specific freight speed set
-- assume speed of 25kmph
update hvt_rail_network
set time_freight = length/((25*1000)/60)
where time_freight = 99999;


-- time cost matrix b/w major towns (open lines)
-- loop

-- origins
-- destinations


-- assuming all lines were open



-- test time cost

-- test via the proposed NICD gauge Interchange
-- Mombasa Port SGR to Malaba (narrow gauge) 
		SELECT X.*, a.country, a.line, a.gauge, a.time_freight, a.status, b.type, b.name FROM pgr_dijkstra(
                'SELECT oid as id, source, target, time_freight AS cost FROM hvt_rail_network',
                1113191,
		1120164,
		false
		) AS X left join
		hvt_rail_network as a on a.oid = X.edge left join
		hvt_rail_nodes as b on b.oid = X.node
		ORDER BY seq;
		
-- test via the disused Kidatu gauge interchange TIZARA -> metre gauge
-- New Kapiri Mposhi to Dodoma
		SELECT X.*, a.country, a.line, a.gauge, a.time_freight, a.status, b.type, b.name FROM pgr_dijkstra(
                'SELECT oid as id, source, target, time_freight AS cost FROM hvt_rail_network',
                3330084,
		2220114,
		false
		) AS X left join
		hvt_rail_network as a on a.oid = X.edge left join
		hvt_rail_nodes as b on b.oid = X.node
		ORDER BY seq;

-- Karogwe -> Arusha 2220112 -> 2221207,
		SELECT X.*, a.country, a.line, a.gauge, a.time_freight, a.status, b.type, b.name FROM pgr_dijkstra(
                'SELECT oid as id, source, target, time_freight AS cost FROM hvt_rail_network',
                2220112,
		2221207,
		false
		) AS X left join
		hvt_rail_network as a on a.oid = X.edge left join
		hvt_rail_nodes as b on b.oid = X.node
		ORDER BY seq;
		

-- Choma 3330130 -> Kitwe 3330033
		SELECT X.*, a.country, a.line, a.gauge, a.time_freight, a.status, b.type, b.name FROM pgr_dijkstra(
                'SELECT oid as id, source, target, time_freight AS cost FROM hvt_rail_network',
                3330130,
		3330033,
		false
		) AS X left join
		hvt_rail_network as a on a.oid = X.edge left join
		hvt_rail_nodes as b on b.oid = X.node
		ORDER BY seq;
		

-- Old Mombasa to Malaba (92 hours)
		SELECT X.*, a.country, a.line, a.gauge, a.time_freight, a.status, b.type, b.name FROM pgr_dijkstra(
                'SELECT oid as id, source, target, time_freight AS cost FROM hvt_rail_network',
                1111512,
		1120164,
		false
		) AS X left join
		hvt_rail_network as a on a.oid = X.edge left join
		hvt_rail_nodes as b on b.oid = X.node
		ORDER BY seq;
		
		-- Tanga to Dar es Salaam (approx 15 hours is 14.3)
		SELECT X.*, a.country, a.line, a.gauge, a.time_freight, a.status, b.type, b.name FROM pgr_dijkstra(
                'SELECT oid as id, source, target, time_freight AS cost FROM hvt_rail_network',
                2221954,
		2222785,
		false
		) AS X left join
		hvt_rail_network as a on a.oid = X.edge left join
		hvt_rail_nodes as b on b.oid = X.node
		ORDER BY seq;

		-- Tanga to Dodoma (approx 22 hours is 23.7)
		SELECT X.*, a.country, a.line, a.gauge, a.time_freight, a.status, b.type, b.name FROM pgr_dijkstra(
                'SELECT oid as id, source, target, time_freight AS cost FROM hvt_rail_network',
                2221954,
		2220114,
		false
		) AS X left join
		hvt_rail_network as a on a.oid = X.edge left join
		hvt_rail_nodes as b on b.oid = X.node
		ORDER BY seq;
		
		-- Tazara Dar es Salaam to New Kapiri Mposhi
		SELECT X.*, a.country, a.line, a.gauge, a.time_freight, a.status, b.type, b.name FROM pgr_dijkstra(
                'SELECT oid as id, source, target, time_freight AS cost FROM hvt_rail_network',
                2221971,
		3330084,
		false
		) AS X left join
		hvt_rail_network as a on a.oid = X.edge left join
		hvt_rail_nodes as b on b.oid = X.node
		ORDER BY seq;
	
-- via the NICD gauge Interchange (under construction)
-- Nakuru SGR to Malaba (narrow gauge) 
-- showing station edges only 
		with tmp as (
		SELECT X.*, a.country, a.line, a.gauge, a.time_freight, a.status, b.type, b.name FROM pgr_dijkstra(
                'SELECT oid as id, source, target, time_freight AS cost FROM hvt_rail_network',
                1113191,
		1110059,
		false
		) AS X left join
		hvt_rail_network as a on a.oid = X.edge left join
		hvt_rail_nodes as b on b.oid = X.node
		ORDER BY seq)
		select node, edge, round(agg_cost::numeric, 2) as agg_time_mins, country, line, gauge, status, type, name from tmp where type in ('station', 'stop', 'halt')
		;
		
		-- Tazara Dar es Salaam (SGR) to Mwanza (SGR)
		SELECT X.*, a.country, a.line, a.gauge, a.time_freight, a.status, b.type, b.name FROM pgr_dijkstra(
                'SELECT oid as id, source, target, time_freight AS cost FROM hvt_rail_network',
                2231958,
		2240009,
		false
		) AS X left join
		hvt_rail_network as a on a.oid = X.edge left join
		hvt_rail_nodes as b on b.oid = X.node
		ORDER BY seq;


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
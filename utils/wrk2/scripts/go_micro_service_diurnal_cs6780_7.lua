
require "socket"
time = socket.gettime()*1000
math.randomseed(time)
math.random(); math.random(); math.random()

-- diurnal pattern all on ath8
-- time: 162s
load_arr_len = 81
load_rates = {'2000', '2200', '2400', '2600', '2800', '3000', '3200', '3400', '3600', '3800', '4000', '4200', '4400', '4600', '4800', '5000', '5200', '5400', '5600', '5800', '6000', '6200', '6400', '6600', '6800', '7000', '7200', '7400', '7600', '7800', '8000', '8200', '8400', '8600', '8800', '9000', '9200', '9400', '9600', '9800', '10000', '9800', '9600', '9400', '9200', '9000', '8800', '8600', '8400', '8200', '8000', '7800', '7600', '7400', '7200', '7000', '6800', '6600', '6400', '6200', '6000', '5800', '5600', '5400', '5200', '5000', '4800', '4600', '4400', '4200', '4000', '3800', '3600', '3400', '3200', '3000', '2800', '2600', '2400', '2200', '2000'}
load_intervals = {'2s', '2s', '2s', '2s', '2s', '2s', '2s', '2s', '2s', '2s', '2s', '2s', '2s', '2s', '2s', '2s', '2s', '2s', '2s', '2s', '2s', '2s', '2s', '2s', '2s', '2s', '2s', '2s', '2s', '2s', '2s', '2s', '2s', '2s', '2s', '2s', '2s', '2s', '2s', '2s', '2s', '2s', '2s', '2s', '2s', '2s', '2s', '2s', '2s', '2s', '2s', '2s', '2s', '2s', '2s', '2s', '2s', '2s', '2s', '2s', '2s', '2s', '2s', '2s', '2s', '2s', '2s', '2s', '2s', '2s', '2s', '2s', '2s', '2s', '2s', '2s', '2s', '2s', '2s', '2s', '2s'}
-- load_intervals = {'60s', '60s', '60s', '20s', '60s', '10s', '10s'}
-- load_rates = {'50k', '80k', '100k', '120k', '110k', '60k', '90k'}

-- diurnal pattern for remote

-- load_arr_len = 44
-- load_rates = {'20k', '22k', '25k', '28k', '31k', '34k', '37k', '40k', '43k', '46k', '49k', '52k', '55k', '58k', '61k', '64k', '67k', '70k', '72k', '74k', '76k', '78k', '80k', '78k', '76k', '74k', '72k', '70k', '68k', '65k', '62k', '59k', '56k', '53k', '50k', '47k', '44k', '41k', '38k', '35k', '32k', '29k', '26k', '23k'}
-- load_intervals = {'60s', '4s', '4s', '4s', '4s', '4s', '4s', '4s', '4s', '4s', '4s', '4s', '4s', '4s', '4s', '4s', '4s', '20s', '20s', '20s', '20s', '20s', '20s', '20s', '20s', '20s', '20s', '20s', '4s', '4s', '4s', '4s', '4s', '4s', '4s', '4s', '4s', '4s', '4s', '4s', '4s', '4s', '4s', '4s'}

-- counter = 0

-- request = function()  
--     -- url_path = math.random(131072)
-- 	-- keep all data in memcached, effectively 2tier
-- 	url_path = math.random(1000)
-- 	-- url_path = math.random(1400000)
-- 	-- url_path = math.random(100)
-- 	-- url_path = zipf(1.01, 10000000)
-- 	-- url_path = zipf(1.01, 1000000)

--     -- url_path = zipf(1.2, 100000)

--     counter = counter + 1
--     -- print("req", url_path)
--     -- return wrk.format(nil, "http://localhost:8088/test/" .. tostring(url_path))
--     return wrk.format(nil, "http://127.0.0.1:8088/test/" .. tostring(url_path))
-- end

function zipf (s, N)
	p = math.random()
	local tolerance = 0.01
	local x = N / 2;
	
	local D = p * (12 * (math.pow(N, 1 - s) - 1) / (1 - s) + 6 - 6 * math.pow(N, -s) + s - math.pow(N, -1 - s) * s)
	
	while true do 
		local m    = math.pow(x, -2 - s);
		local mx   = m   * x;
		local mxx  = mx  * x;
		local mxxx = mxx * x;

		local a = 12 * (mxxx - 1) / (1 - s) + 6 * (1 - mxx) + (s - (mx * s)) - D
		local b = 12 * mxx + 6 * (s * mx) + (m * s * (s + 1))
		local newx = math.max(1, x - a / b)
		if math.abs(newx - x) <= tolerance then
			return math.floor(newx)
		end
		x = newx
	end
end


-- response = function(status, headers, body)
-- 	-- print("ngx-end")
-- 	-- print(headers["ngx-end"])
-- 	if headers["X-cache"] == "MISS" then
-- 		return 0, headers["request-latency"], headers["get-latency"], headers["find-latency"], headers["set-latency"], headers['ngx-end']
-- 	else
-- 		return 1, headers["request-latency"], headers["get-latency"], 0, 0, headers['ngx-end']
-- 	end

--     -- return headers["X-cache"]
-- -- -- end
-- --     if headers["X-cache"] == "MISS" then
-- --         print("MISS", headers["mmc-get-start"], headers["mmc-get-end"], headers["mongo-find-start"], headers["mongo-find-end"], headers["mmc-set-start"], headers["mmc-set-end"])
-- --     else
-- --         print("HIT", headers["mmc-get-start"], headers["mmc-get-end"])
-- --     end
-- end

  

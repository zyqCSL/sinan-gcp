-- require "socket"
-- time = socket.gettime()*1000
local chronos = require("chronos")

request = function()
	local time_ns  = chronos.nanotime() * 1000000000   
    return wrk.format(nil, "http://127.0.0.1:5000/hotels?inDate=2015-04-09&outDate=2015-04-10&initTime=" .. tostring(time_ns))
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

  

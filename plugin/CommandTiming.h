// SPDX-License-Identifier: GPL-3.0-only
#pragma once
#include "json.h"

// Measures the existing service block, not CPU time or the complete RPC.
static bool attachServiceTiming(json::Value& response,bool enabled,const std::string& command,
    bool menuService,unsigned long thread,unsigned __int64 created,unsigned long frame,
    double queued,double started,double finished){
    if(!enabled||response.type!=json::Value::OBJECT||!response.object.count("result")||
        response.object["result"].type!=json::Value::OBJECT)return false;
    if(!_finite(queued)||!_finite(started)||!_finite(finished)||queued<0||started<queued||finished<started||!thread)return false;
    json::Value timing=json::Value::obj();
    timing.object["schema_version"]=json::Value(1.0);timing.object["command"]=json::Value(command);
    timing.object["menu_service"]=json::Value::flag(menuService);timing.object["thread_id"]=json::Value((double)thread);
    std::ostringstream stamp;stamp<<created;
    timing.object["created_filetime"]=created?json::Value(stamp.str()):json::Value();
    timing.object["identity_verified"]=json::Value::flag(created!=0);timing.object["frame"]=json::Value((double)frame);
    timing.object["queued_qpc_ms"]=json::Value(queued);timing.object["started_qpc_ms"]=json::Value(started);timing.object["finished_qpc_ms"]=json::Value(finished);
    timing.object["queue_wait_ms"]=json::Value(started-queued);timing.object["service_ms"]=json::Value(finished-started);
    timing.object["scope"]=json::Value(std::string("Wall time of execute/response assignment/debug log; excludes telemetry attachment, event signal, network JSON serialization/send and client transport. Not CPU time."));
    response.object["result"].object["_probe_service"]=timing;return true;
}

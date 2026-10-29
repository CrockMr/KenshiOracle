// SPDX-License-Identifier: GPL-3.0-only
#pragma once
#include "OracleHandleIds.h"

namespace oracle {
// The public offset is ADDITIONAL to the native tracking pivot. Calibration
// measures that pivot instead of assuming a character height or fixed bias.
inline float calibratedCameraFollowComponent(double currentOffset,double requestedCenter,double observedCenter){
    if(!_finite(currentOffset)||!_finite(requestedCenter)||!_finite(observedCenter)||fabs(currentOffset)>1e7||fabs(requestedCenter)>1e7||fabs(observedCenter)>1e7)
        throw Error("invalid_request","camera calibration inputs must be finite and within coordinate bounds");
    double offset=currentOffset+(requestedCenter-observedCenter);
    if(!_finite(offset)||fabs(offset)>1e7)throw Error("invalid_request","restored camera follow offset exceeds coordinate bounds");
    return (float)offset;
}
inline void calibratedCameraFollowOffset(const double current[3],const double center[3],const double observed[3],float offset[3]){
    float next[3];for(int i=0;i<3;++i)next[i]=calibratedCameraFollowComponent(current[i],center[i],observed[i]);
    for(int i=0;i<3;++i)offset[i]=next[i];
}
struct CameraRestoreSpec {
    float center[3],orientation[4],zoom;
    double speed;
    bool freeCamera,edgeScrolling,paused;
    std::string followId;
};
inline void cameraRestoreVector(const json::Value& params,const char* key,float out[3]){
    const json::Value& v=field(params,key);if(v.type!=json::Value::ARRAY||v.array.size()!=3)throw Error("invalid_request",std::string(key)+" must have three numbers");
    for(int i=0;i<3;++i){if(v.array[i].type!=json::Value::NUMBER||!_finite(v.array[i].number)||fabs(v.array[i].number)>1e7)throw Error("invalid_request","invalid camera coordinate");out[i]=(float)v.array[i].number;}
}
inline CameraRestoreSpec readCameraRestoreSpec(const json::Value& params){
    const char* allowed[]={"camera_center","camera_position","camera_orientation","camera_zoom","free_camera","edge_scrolling","speed","paused","camera_follow_id"};keys(params,allowed,9);CameraRestoreSpec out;
    cameraRestoreVector(params,"camera_center",out.center);if(params.object.count("camera_position")){float unused[3];cameraRestoreVector(params,"camera_position",unused);}
    const json::Value& rotation=field(params,"camera_orientation");if(rotation.type!=json::Value::ARRAY||rotation.array.size()!=4)throw Error("invalid_request","camera_orientation must be [w,x,y,z]");double norm=0;
    for(int i=0;i<4;++i){if(rotation.array[i].type!=json::Value::NUMBER||!_finite(rotation.array[i].number)||fabs(rotation.array[i].number)>1.001)throw Error("invalid_request","invalid camera quaternion");out.orientation[i]=(float)rotation.array[i].number;norm+=rotation.array[i].number*rotation.array[i].number;}
    if(fabs(norm-1)>0.01)throw Error("invalid_request","camera quaternion must be normalized");
    out.zoom=(float)number(params,"camera_zoom",-1e7,1e7);out.speed=number(params,"speed",0.000001,5);out.freeCamera=flag(params,"free_camera");out.edgeScrolling=flag(params,"edge_scrolling");out.paused=flag(params,"paused");
    if(!out.freeCamera&&out.zoom>=0)throw Error("invalid_request","strategy camera_zoom must be negative local Z");
    if(params.object.count("camera_follow_id")&&params.at("camera_follow_id").type!=json::Value::NIL){out.followId=text(params,"camera_follow_id",maximumSavedHandleIdBytes);if(parseSavedHandleId(out.followId).type!=1)throw Error("invalid_request","camera follow ID must identify a character");}
    return out;
}
class CameraRestorePending {
public:
    std::string token,followRaw;
    json::Value params;
    unsigned long epoch;
    CameraRestorePending():epoch(0){}
    bool active() const {return !token.empty();}
    void clear(){token.clear();followRaw.clear();json::Value empty;params.swap(empty);epoch=0;}
    void begin(const json::Value& wanted,const std::string& nextToken,unsigned long worldEpoch,const std::string& rawFollow){
        if(active())throw Error("camera_restore_busy","a scene-control calibration is already prepared");
        CameraRestoreSpec spec=readCameraRestoreSpec(wanted);
        if(nextToken.empty()||nextToken.size()>200||nextToken.find('\0')!=std::string::npos)throw Error("invalid_request","invalid camera restore token");
        if(!rawFollow.empty()&&parseSavedHandleId(rawFollow).type!=1)throw Error("invalid_request","invalid prepared camera follow ID");
        if(spec.followId.empty()!=rawFollow.empty())throw Error("invalid_request","prepared follow proof disagrees with requested follow presence");
        json::Value nextParams=wanted;std::string nextRaw=rawFollow,nextId=nextToken;params.swap(nextParams);followRaw.swap(nextRaw);token.swap(nextId);epoch=worldEpoch;
    }
    void require(const std::string& candidate,unsigned long worldEpoch) const {
        if(!active()||candidate!=token||epoch!=worldEpoch)throw Error("camera_restore_token_invalid","camera restore token is absent, stale, or belongs to another world epoch");
    }
    void synchronize(unsigned long worldEpoch){if(active()&&epoch!=worldEpoch)clear();}
    void swap(CameraRestorePending& other){token.swap(other.token);followRaw.swap(other.followRaw);params.swap(other.params);std::swap(epoch,other.epoch);}
};
}

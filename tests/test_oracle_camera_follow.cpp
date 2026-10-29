// SPDX-License-Identifier: GPL-3.0-only
#include "../plugin/OracleCameraFollow.h"
#include "../plugin/OracleSavedOrigins.h"
#include <iostream>
#include <limits>
static unsigned checks=0;
static void require(bool v){++checks;if(!v)throw std::runtime_error("camera calibration assertion failed");}
static json::Value fixture(){return json::Parser("{\"camera_center\":[-50978.796875,1541.7958984375,2932.4765625],\"camera_orientation\":[1,0,0,0],\"camera_zoom\":-88,\"free_camera\":false,\"edge_scrolling\":true,\"speed\":1,\"paused\":true,\"camera_follow_id\":\"hand:1:1:751953152:1:3279785216\"}").parse();}
static void badMath(double current,double wanted,double observed){bool failed=false;try{oracle::calibratedCameraFollowComponent(current,wanted,observed);}catch(const oracle::Error& e){failed=e.code=="invalid_request";}require(failed);}
static void badSpec(const json::Value& v){bool failed=false;try{oracle::readCameraRestoreSpec(v);}catch(const oracle::Error& e){failed=e.code=="invalid_request";}require(failed);}
static void badToken(const oracle::CameraRestorePending& p,const std::string& token,unsigned long epoch){bool failed=false;try{p.require(token,epoch);}catch(const oracle::Error& e){failed=e.code=="camera_restore_token_invalid";}require(failed);}
int main(){try{
    require(_MSC_VER==1600&&sizeof(void*)==8);
    const float wanted=1541.7958984375f,baseline=1542.73193359375f,oldExtra=9.800048828125f;
    float extra=oracle::calibratedCameraFollowComponent(0,wanted,baseline);require(extra<0&&baseline+extra==wanted);
    require(oracle::calibratedCameraFollowComponent(extra,wanted,wanted)==extra);
    require(oracle::calibratedCameraFollowComponent(oldExtra,wanted,baseline+oldExtra)==extra);
    // Arbitrary native bases prove that neither actor coordinates nor a magic
    // vertical bias is needed; the measured correction works in all axes.
    const double base[3]={-51000,1530,2900},old[3]={4,-7,18},desired[3]={-50978.796875,wanted,2932.4765625};double observed[3];float out[3];
    for(int i=0;i<3;++i)observed[i]=base[i]+old[i];oracle::calibratedCameraFollowOffset(old,desired,observed,out);
    for(int i=0;i<3;++i)require((float)base[i]+out[i]==(float)desired[i]);require(old[0]==4&&base[1]==1530);
    require(oracle::calibratedCameraFollowComponent(0,1e7,0)==1e7f);require(oracle::calibratedCameraFollowComponent(0,-1e7,0)==-1e7f);require(oracle::calibratedCameraFollowComponent(1e7,0,1e7)==0);
    badMath(0,1e7,-1);badMath(0,-1e7,1);badMath(1e7,1,0);badMath(1e7+1,0,0);badMath(0,1e7+1,0);badMath(0,0,1e7+1);
    const double invalid[]={std::numeric_limits<double>::infinity(),-std::numeric_limits<double>::infinity(),std::numeric_limits<double>::quiet_NaN()};
    for(int i=0;i<3;++i){badMath(invalid[i],0,0);badMath(0,invalid[i],0);badMath(0,0,invalid[i]);}
    double badObserved[3]={1,2,invalid[2]};out[0]=11;out[1]=12;out[2]=13;bool failed=false;
    try{oracle::calibratedCameraFollowOffset(old,desired,badObserved,out);}catch(const oracle::Error& e){failed=e.code=="invalid_request";}require(failed&&out[0]==11&&out[1]==12&&out[2]==13);
    json::Value p=fixture();oracle::CameraRestoreSpec spec=oracle::readCameraRestoreSpec(p);require(spec.center[0]==-50978.796875f&&spec.zoom==-88&&spec.speed==1&&!spec.freeCamera&&spec.edgeScrolling&&spec.paused);
    badSpec(json::Value());badSpec(json::Value::obj());const char* required[]={"camera_center","camera_orientation","camera_zoom","free_camera","edge_scrolling","speed","paused"};
    for(int i=0;i<7;++i){json::Value bad=p;bad.object.erase(required[i]);badSpec(bad);}
    json::Value bad=p;bad.object["unknown"]=json::Value();badSpec(bad);bad=p;bad.object["speed"]=json::Value::flag(true);badSpec(bad);bad=p;bad.object["speed"]=json::Value(0.0);badSpec(bad);bad=p;bad.object["speed"]=json::Value(5.1);badSpec(bad);
    bad=p;bad.object["paused"]=json::Value(1.0);badSpec(bad);bad=p;bad.object["free_camera"]=json::Value();badSpec(bad);bad=p;bad.object["edge_scrolling"]=json::Value(std::string("false"));badSpec(bad);
    bad=p;bad.object["camera_center"].array.pop_back();badSpec(bad);bad=p;bad.object["camera_center"].array[2]=json::Value(1e7+1);badSpec(bad);bad=p;bad.object["camera_position"]=json::Value::arr();badSpec(bad);
    bad=p;bad.object["camera_orientation"].array[0]=json::Value(.5);badSpec(bad);bad=p;bad.object["camera_orientation"].array[0]=json::Value(1.002);badSpec(bad);bad=p;bad.object["camera_zoom"]=json::Value(0.0);badSpec(bad);bad.object["free_camera"]=json::Value::flag(true);require(oracle::readCameraRestoreSpec(bad).zoom==0);
    bad=p;bad.object["camera_follow_id"]=json::Value(std::string("hand:34:1:2:0:0"));badSpec(bad);bad=p;bad.object["camera_follow_id"]=json::Value(std::string("hand:1:1:2:3:4294967296"));badSpec(bad);bad=p;bad.object["camera_follow_id"]=json::Value::flag(false);badSpec(bad);
    bad=p;bad.object["camera_follow_id"]=json::Value();require(oracle::readCameraRestoreSpec(bad).followId.empty());bad.object.erase("camera_follow_id");require(oracle::readCameraRestoreSpec(bad).followId.empty());
    const std::string raw="hand:1:12:123:1:3279785216";oracle::CameraRestorePending pending;badToken(pending,"absent",1);pending.begin(p,"first",1,raw);require(pending.active()&&pending.followRaw==raw&&pending.epoch==1);
    p.object["speed"]=json::Value(5.0);require(pending.params.at("speed").number==1);pending.require("first",1);badToken(pending,"other",1);badToken(pending,"first",2);
    failed=false;try{pending.begin(fixture(),"second",1,raw);}catch(const oracle::Error& e){failed=e.code=="camera_restore_busy";}require(failed&&pending.token=="first");
    pending.synchronize(1);require(pending.active());pending.synchronize(2);require(!pending.active()&&pending.params.type==json::Value::NIL&&pending.followRaw.empty());badToken(pending,"first",2);
    failed=false;bad=fixture();bad.object["extra"]=json::Value();try{pending.begin(bad,"bad",2,raw);}catch(const oracle::Error& e){failed=e.code=="invalid_request";}require(failed&&!pending.active());
    failed=false;try{pending.begin(fixture(),std::string(201,'t'),2,raw);}catch(const oracle::Error& e){failed=e.code=="invalid_request";}require(failed&&!pending.active());
    failed=false;try{pending.begin(fixture(),"no-proof",2,std::string());}catch(const oracle::Error& e){failed=e.code=="invalid_request";}require(failed&&!pending.active());
    bad=fixture();bad.object["camera_follow_id"]=json::Value();pending.begin(bad,"none",2,std::string());require(pending.active()&&pending.followRaw.empty());pending.clear();badToken(pending,"none",2);
    oracle::SavedOrigins origins;oracle::SavedOriginEpoch epoch;int first=0,second=0;epoch.synchronize(&first,true,origins);pending.begin(fixture(),"world",epoch.serial(),raw);
    epoch.synchronize(&first,true,origins);pending.synchronize(epoch.serial());require(pending.active());epoch.synchronize(&first,false,origins);pending.synchronize(epoch.serial());require(!pending.active());
    epoch.synchronize(&first,true,origins);pending.begin(fixture(),"save",epoch.serial(),raw);epoch.expectLoad("KenshiProbe_test",origins);pending.synchronize(epoch.serial());require(!pending.active());
    epoch.synchronize(&first,true,origins);pending.begin(fixture(),"replacement",epoch.serial(),raw);epoch.synchronize(&second,true,origins);pending.synchronize(epoch.serial());require(!pending.active());
    std::cout<<"{\"passed\":true,\"checks\":"<<checks<<",\"measured_additional_offset\":true,\"toolset\":\"v100 x64\"}\n";return 0;
}catch(const std::exception& e){std::cerr<<e.what()<<"\n";return 1;}}

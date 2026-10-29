// SPDX-License-Identifier: GPL-3.0-only
#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#define _WIN32_WINNT 0x0601
#include <winsock2.h>
#include <windows.h>
#include <Debug.h>
#include <core/Functions.h>
#include <kenshi/GameWorld.h>
#include <kenshi/Character.h>
#include <kenshi/Faction.h>
#include <kenshi/Kenshi.h>
#include <kenshi/Globals.h>
#include <kenshi/SaveManager.h>
#include <kenshi/Renderer.h>
#include <kenshi/NavMesh.h>
#include <kenshi/SharedKing.h>
#include <kenshi/Town.h>
#include <kenshi/CameraClass.h>
#include <kenshi/CharMovement.h>
#include <kenshi/OptionsHolder.h>
#include <kenshi/InputHandler.h>
#include <kenshi/PhysicsActual.h>
#include <kenshi/AI/AI.h>
#include <kenshi/ResourceLoader.h>
#include <kenshi/SaveFileSystem.h>
#include <kenshi/NavMeshGenerator.h>
#include <kenshi/ZoneManager.h>
#include <kenshi/MedicalSystem.h>
#include <kenshi/HavokCharacter.h>
#include <deque>
#include <algorithm>
#include <boost/shared_ptr.hpp>
#include "json.h"
#include "NavTelemetry.h"
#include "CallTelemetry.h"
#include "ThreadIdentity.h"
#include "FunctionProbeTarget.h"
#include "CommandTiming.h"
#include "CharsTelemetry.h"
#include "OriginalLoopInvocation.h"
#include "OriginalRendererInvocation.h"
#include "OriginalBoolInvocation.h"
#include "LoadedModuleExport.h"
#include "StatisticsDetail.h"
#pragma comment(lib,"Ws2_32.lib")
using json::Value;
static CRITICAL_SECTION lock;
struct Guard { Guard(){EnterCriticalSection(&lock);} ~Guard(){LeaveCriticalSection(&lock);} };
struct Work {
    Value request, response; HANDLE done; bool cancelled;double queuedAt;
    Work(const Value& r):request(r),done(CreateEvent(0,TRUE,FALSE,0)),cancelled(false),queuedAt(0) {if(!done)throw std::runtime_error("event allocation");}
    ~Work(){CloseHandle(done);}
};
static std::deque<boost::shared_ptr<Work> > queue;
struct Sample { double ms, mainAI, navMs, navMax; unsigned long index, navCalls; NavBuckets navThreads; CallBuckets functionCalls; unsigned long functionNested; };
static std::deque<Sample> samples;
static LARGE_INTEGER frequency, previous;
static double aiMain=0;
static CharsBuckets charsBucket;
static CharsHistory charsHistory;
static CallBuckets functionBucket;
static bool functionProfiling=false,functionThreadCpu=false;
static bool mainServiceInstalled=false,rendererServiceInstalled=false;
static bool commandTimingEnabled=false;
static double functionCpuReadMeanUs=0;
static FunctionProbeTarget functionTarget=FunctionProbePeriodic;
static std::string functionTargetSource="default";
static unsigned long functionNested=0;
__declspec(thread) static unsigned int functionDepth=0;
__declspec(thread) static ThreadIdentityState functionIdentity={0,0};
__declspec(thread) static ThreadIdentityState serviceIdentity={0,0};
__declspec(thread) static ThreadIdentityState charsIdentity={0,0};
static double navMs=0, navMax=0;
static unsigned long navCalls=0;
static NavBuckets navThreads;
static const int slowNavCapacity=32;
static const double slowNavThreshold=10.0;
static SlowNavCall slowNav[slowNavCapacity];
static int slowNavNext=0, slowNavCount=0;
static const char* navKinds[3]={"game_thread","other_threads","unclassified"};
static bool navProfiling=false;
static bool navThreadCpu=false;
static double navCpuReadMeanUs=0;
static unsigned long frame=0;
static unsigned long publishedFrame=0;
static double publishedTime=0;
static unsigned long serviceFrame=0;
static double serviceTime=0;
static DWORD serviceThread=0, gameThread=0;
static bool loadPending=false;
static bool loadPausePending=false;
static std::string lastRequestedSave;
static bool sceneEdgeOwned=false,sceneEdgePrevious=true;
static bool profiling=false;
static void (*originalLoop)(GameWorld*,float)=0;
static void (*originalChars)(GameWorld*)=0;
static void (*originalAI)(AI*,float)=0;
static void (*originalCharsUT)(GameWorld*)=0;
static void (*originalZoneRendertime)(ZoneManager*,const Ogre::Vector3&)=0;
static void (*originalMedicalPeriodic)(MedicalSystem*)=0;
static void (*originalHavokUpdate)(HavokCharacter*,float)=0;
static void (*originalRenderer)(Renderer*)=0;
static bool (*originalRootFrame)(Ogre::Root*)=0;
static LoadedModuleExport rootFrameBinding;
static const char* rootFrameSymbol="?renderOneFrame@Root@Ogre@@QEAA_NXZ";
typedef bool (*PathFunction)(NavMesh*,unsigned int,const hkVector4f&,unsigned int,const hkVector4f&,float,float,bool,hkArray<EdgePathNode,hkContainerHeapAllocator>&);
static PathFunction originalPath=0;
static double now(){LARGE_INTEGER t;QueryPerformanceCounter(&t);return 1000.0*t.QuadPart/frequency.QuadPart;}
static bool threadCpuMs(double& user,double& kernel,unsigned __int64* identity=0){
    FILETIME created,exited,k,u;if(!GetThreadTimes(GetCurrentThread(),&created,&exited,&k,&u))return false;
    ULARGE_INTEGER ku,uu;ku.LowPart=k.dwLowDateTime;ku.HighPart=k.dwHighDateTime;uu.LowPart=u.dwLowDateTime;uu.HighPart=u.dwHighDateTime;
    if(identity){ULARGE_INTEGER c;c.LowPart=created.dwLowDateTime;c.HighPart=created.dwHighDateTime;*identity=c.QuadPart;}
    user=(double)uu.QuadPart*0.0001;kernel=(double)ku.QuadPart*0.0001;return true;
}
static bool currentThreadCreation(unsigned __int64& creation){double user=0,kernel=0;return threadCpuMs(user,kernel,&creation);}
static void charsHook(GameWorld* world){
    DWORD thread=GetCurrentThreadId();unsigned __int64 creation=cachedThreadCreation(charsIdentity,currentThreadCreation);
    double started=now();originalChars(world);double finished=now();
    Guard g;double acquired=now();aiMain+=acquired-started;charsBucket.record(thread,creation,started,finished,acquired);
}
template<typename Invocation> static void profileFunction(const Invocation& invoke){
    CallDepthGuard depth(functionDepth);
    if(!depth.outermost){{Guard g;++functionNested;}invoke();return;}
    double beforeUser=0,beforeKernel=0,afterUser=0,afterKernel=0;
    unsigned __int64 creation=cachedThreadCreation(functionIdentity,currentThreadCreation);
    bool before=functionThreadCpu&&threadCpuMs(beforeUser,beforeKernel);
    DWORD thread=GetCurrentThreadId();double t=now();
    invoke();double elapsed=now()-t;
    bool cpu=before&&threadCpuMs(afterUser,afterKernel)&&afterUser>=beforeUser&&afterKernel>=beforeKernel;
    Guard g;functionBucket.record(thread,elapsed,cpu,afterUser-beforeUser,afterKernel-beforeKernel,creation);
}
struct AIInvocation {AI* ai;float dt;void operator()() const{originalAI(ai,dt);}};
struct WorldInvocation {GameWorld* world;void operator()() const{originalCharsUT(world);}};
struct ZoneInvocation {ZoneManager* zones;const Ogre::Vector3& camera;void operator()() const{originalZoneRendertime(zones,camera);}};
struct MedicalInvocation {MedicalSystem* medical;void operator()() const{originalMedicalPeriodic(medical);}};
struct HavokInvocation {HavokCharacter* character;float dt;void operator()() const{originalHavokUpdate(character,dt);}};
static void aiFunctionHook(AI* ai,float dt){AIInvocation call={ai,dt};profileFunction(call);}
static void charsUTHook(GameWorld* world){WorldInvocation call={world};profileFunction(call);}
static void zoneRendertimeHook(ZoneManager* zones,const Ogre::Vector3& camera){ZoneInvocation call={zones,camera};profileFunction(call);}
static void medicalPeriodicHook(MedicalSystem* medical){MedicalInvocation call={medical};profileFunction(call);}
static void havokUpdateHook(HavokCharacter* character,float dt){HavokInvocation call={character,dt};profileFunction(call);}
static bool rootFrameHook(Ogre::Root* root){OriginalBoolInvocation<Ogre::Root> call={originalRootFrame,root,false};profileFunction(call);return call.result;}
static bool pathHook(NavMesh* mesh,unsigned int startKey,const hkVector4f& start,unsigned int goalKey,const hkVector4f& goal,float radius,float water,bool hierarchical,hkArray<EdgePathNode,hkContainerHeapAllocator>& output){
    SlowNavCall call;call.thread=GetCurrentThreadId();{Guard g;call.startFrame=publishedFrame;call.gameThread=gameThread;}
    call.kind=!call.gameThread?2:(call.thread==call.gameThread?0:1);
    call.outputSizeBefore=output.m_size;
    _mm_storeu_ps(call.startVector,start.m_quad);_mm_storeu_ps(call.goalVector,goal.m_quad);
    double beforeUser=0,beforeKernel=0,afterUser=0,afterKernel=0;bool cpuBefore=navThreadCpu&&threadCpuMs(beforeUser,beforeKernel);
    double t=now();bool result=originalPath(mesh,startKey,start,goalKey,goal,radius,water,hierarchical,output);double elapsed=now()-t;
    call.outputSizeAfter=output.m_size;
    call.cpuAvailable=cpuBefore&&threadCpuMs(afterUser,afterKernel)&&afterUser>=beforeUser&&afterKernel>=beforeKernel;
    call.cpuUserMs=afterUser-beforeUser;call.cpuKernelMs=afterKernel-beforeKernel;
    {Guard g;navMs+=elapsed;navMax=std::max(navMax,elapsed);++navCalls;navThreads.ms[call.kind]+=elapsed;navThreads.maximum[call.kind]=std::max(navThreads.maximum[call.kind],elapsed);++navThreads.calls[call.kind];
        int r=result?1:0;navThreads.returnedMs[r]+=elapsed;navThreads.returnedMax[r]=std::max(navThreads.returnedMax[r],elapsed);++navThreads.returnedCalls[r];if(hierarchical)++navThreads.returnedHierarchical[r];
        if(elapsed>=slowNavThreshold){++navThreads.slowCalls;call.started=t;call.elapsed=elapsed;call.completionFrame=publishedFrame;call.startKey=startKey;call.goalKey=goalKey;call.radius=radius;call.water=water;call.hierarchical=hierarchical;call.result=result;slowNav[slowNavNext]=call;slowNavNext=(slowNavNext+1)%slowNavCapacity;slowNavCount=std::min(slowNavCount+1,slowNavCapacity);}
    }return result;
}
static Value error(const Value& id,const char* message,const char* code="invalid_request"){Value r=Value::obj();r.object["id"]=id;Value e=Value::obj();e.object["code"]=Value(std::string(code));e.object["message"]=Value(std::string(message));r.object["error"]=e;return r;}
static Value vectorJSON(const Ogre::Vector3& pos){Value v=Value::arr();v.array.push_back(Value(pos.x));v.array.push_back(Value(pos.y));v.array.push_back(Value(pos.z));return v;}
static CameraClass* sceneCamera(GameWorld* world){CameraClass* camera=world&&world->player?world->player->getCamera():0;if(!camera||!camera->isInitialised())throw std::runtime_error("camera unavailable");return camera;}
static TownList* townList(){if(!shou||!shou->townList)throw std::runtime_error("town list unavailable");return shou->townList;}
static void controlSceneCamera(){if(!::options)throw std::runtime_error("camera options unavailable");if(!sceneEdgeOwned){sceneEdgePrevious=::options->edgeScrolling;sceneEdgeOwned=true;}::options->edgeScrolling=false;}
static void restoreSceneCamera(){if(sceneEdgeOwned&&::options){::options->edgeScrolling=sceneEdgePrevious;sceneEdgeOwned=false;}}
#include "BattleScene.h"
#include "SceneSnapshots.h"
#include "ThreadRoles.h"
#include "OracleState.h"
static Value sceneState(GameWorld* world,bool threadDetails=false){
    CameraClass* camera=sceneCamera(world);Value v=Value::obj();v.object["camera_center"]=vectorJSON(camera->getCenter());v.object["camera_position"]=vectorJSON(camera->getCameraPos());v.object["free_camera"]=Value::flag(camera->isFreeCameraMode());
    v.object["loaded_character_count"]=Value((double)world->getCharacterUpdateList().size());v.object["active_town_count"]=Value((double)townList()->getActiveTowns().size());v.object["frame"]=Value((double)frame);v.object["paused"]=Value::flag(world->isPaused());v.object["frame_speed_multiplier"]=Value((double)world->getFrameSpeedMultiplier());
    v.object["edge_scrolling"]=::options?Value::flag(::options->edgeScrolling):Value();v.object["scene_camera_control_owned"]=Value::flag(sceneEdgeOwned);v.object["battle"]=battle::state(world);
    if(::key){Value input=Value::obj(),pos=Value::arr(),absPos=Value::arr();pos.array.push_back(_finite(::key->mPos.x)?Value(::key->mPos.x):Value());pos.array.push_back(_finite(::key->mPos.y)?Value(::key->mPos.y):Value());absPos.array.push_back(_finite(::key->mPosAbs.x)?Value(::key->mPosAbs.x):Value());absPos.array.push_back(_finite(::key->mPosAbs.y)?Value(::key->mPosAbs.y):Value());input.object["mPos"]=pos;input.object["mPosAbs"]=absPos;input.object["up"]=Value::flag(::key->up);input.object["down"]=Value::flag(::key->down);input.object["left"]=Value::flag(::key->left);input.object["right"]=Value::flag(::key->right);input.object["ctrl"]=Value::flag(::key->ctrl);v.object["input"]=input;}
    TimeOfDay stamp=world->getTimeStamp_inGameHours();double hours=stamp.getTotalHours(),raw=world->getTimeStamp(),length=world->getLengthOfHourInRealSeconds();v.object["game_total_hours"]=_finite(hours)?Value(hours):Value();v.object["game_time_stamp"]=_finite(raw)?Value(raw):Value();v.object["game_hour_real_seconds"]=_finite(length)?Value(length):Value();v.object["observed_qpc_ms"]=Value(now());if(threadDetails)v.object["sdk_threads"]=sdkThreadRoles(world);oracle::addCameraControl(world,v);return v;
}
static double numeric(const Value& p,const char* key,double low,double high,bool integer){const Value& v=p.at(key);if(v.type!=Value::NUMBER||v.number<low||v.number>high||(integer&&floor(v.number)!=v.number))throw std::runtime_error("parameter out of range or wrong type");return v.number;}
static bool optionalFlag(const Value& p,const char* key){
    if(!p.object.count(key))return false;const Value& v=p.at(key);if(v.type==Value::NIL)return false;if(v.type!=Value::BOOL)throw std::runtime_error(std::string(key)+" must be bool");return v.boolean;
}
#include "FrameStatistics.h"
static Value execute(GameWorld* world,const Value& r){
    const Value& cmd=r.at("command");if(cmd.type!=Value::STRING)throw std::runtime_error("command must be string");const Value& p=r.at("params");if(p.type!=Value::OBJECT)throw std::runtime_error("params must be object");Value out=Value::obj();
    oracle::synchronizeWorld(world);bool ready=oracle::worldReady(world);
    if(cmd.str=="ping"){out.object["schema_version"]=Value(std::string(oracle::schemaVersion));out.object["process_id"]=Value((double)GetCurrentProcessId());out.object["instance_id"]=Value(oracle::instanceId);out.object["oracle_available"]=Value::flag(true);out.object["ogre_render_one_frame_profiling"]=Value::flag(functionProfiling&&functionTarget==FunctionProbeOgreRootFrame);out.object["function_binding_source"]=functionTarget==FunctionProbeOgreRootFrame?Value(std::string("loaded_module_export")):Value();out.object["function_binding_module_path"]=functionTarget==FunctionProbeOgreRootFrame?Value(rootFrameBinding.modulePath):Value();out.object["function_binding_address"]=functionTarget==FunctionProbeOgreRootFrame?Value(rootFrameBinding.addressHex):Value();out.object["function_binding_symbol"]=functionTarget==FunctionProbeOgreRootFrame?Value(std::string(rootFrameSymbol)):Value();out.object["main_loop_gpu_sensitive_profiling"]=Value::flag(functionProfiling&&reusesMainServiceHook(functionTarget));out.object["renderer_update_profiling"]=Value::flag(functionProfiling&&reusesRendererServiceHook(functionTarget));out.object["function_hook_reuses_service"]=Value::flag(functionProfiling&&reusesServiceHook(functionTarget));out.object["dedicated_system_hook_count"]=Value((double)((profiling?1:0)+(navProfiling?1:0)+(functionProfiling&&!reusesServiceHook(functionTarget)?1:0)));out.object["service_hook_count"]=Value((double)((mainServiceInstalled?1:0)+(rendererServiceInstalled?1:0)));out.object["installed_hook_count"]=Value((double)((profiling?1:0)+(navProfiling?1:0)+(functionProfiling&&!reusesServiceHook(functionTarget)?1:0)+(mainServiceInstalled?1:0)+(rendererServiceInstalled?1:0)));out.object["chars_update_split_profiling"]=Value::flag(profiling);out.object["chars_update_bucket_bytes"]=Value((double)sizeof(CharsBuckets));out.object["telemetry_sample_bytes"]=Value((double)sizeof(Sample));out.object["chars_update_history_bytes"]=Value((double)sizeof(CharsHistory));out.object["command_service_timing_available"]=Value::flag(true);out.object["command_service_timing_enabled"]=Value::flag(commandTimingEnabled);out.object["frame_stats_aggregates_available"]=Value::flag(true);out.object["plugin_version"]=Value(std::string("0.9.5"));out.object["game_version"]=Value(KenshiLib::GetKenshiVersion().ToString());out.object["frame"]=Value((double)frame);out.object["timestamp_ms"]=Value(now());out.object["world_ready"]=Value::flag(ready);out.object["navmesh_profiling"]=Value::flag(navProfiling);out.object["charsUpdate_profiling"]=Value::flag(profiling);out.object["charsUpdateUT_profiling"]=Value::flag(functionProfiling&&functionTarget==FunctionProbeCharsUT);out.object["zone_rendertime_thread_profiling"]=Value::flag(functionProfiling&&functionTarget==FunctionProbeZoneRendertime);out.object["medical_periodic_update_profiling"]=Value::flag(functionProfiling&&functionTarget==FunctionProbeMedicalPeriodic);out.object["havok_character_update_profiling"]=Value::flag(functionProfiling&&functionTarget==FunctionProbeHavokUpdate);out.object["sdk_thread_roles_available"]=Value::flag(true);out.object["camera_load_edge_lock_available"]=Value::flag(true);out.object["test_save_pause_on_ready_available"]=Value::flag(true);out.object["set_game_speed_preserve_pause_available"]=Value::flag(true);out.object["load_pause_pending"]=Value::flag(loadPausePending);out.object["ai_periodic_update_profiling"]=Value::flag(functionProfiling&&functionTarget==FunctionProbePeriodic);out.object["ai_update4_frame_profiling"]=Value::flag(functionProfiling&&functionTarget==FunctionProbeFourFrame);out.object["ai_profiling"]=Value::flag(functionProfiling&&isAIProbe(functionTarget));out.object["ai_profiled_function"]=isAIProbe(functionTarget)?Value(std::string(functionProbeName(functionTarget))):Value();out.object["ai_probe_target_valid"]=Value::flag(isAIProbe(functionTarget));out.object["ai_thread_identity_mode"]=isAIProbe(functionTarget)?Value(std::string("tls_creation_once")):Value();out.object["ai_thread_identity_independent_of_cpu"]=Value::flag(isAIProbe(functionTarget));out.object["ai_thread_cpu_enabled"]=Value::flag(functionThreadCpu&&isAIProbe(functionTarget));out.object["ai_thread_cpu_startup_read_mean_us"]=functionThreadCpu&&isAIProbe(functionTarget)?Value(functionCpuReadMeanUs):Value();out.object["function_profiling"]=Value::flag(functionProfiling);out.object["profiled_function"]=functionTarget==FunctionProbeInvalid?Value():Value(std::string(functionProbeName(functionTarget)));out.object["function_probe_target_valid"]=Value::flag(functionTarget!=FunctionProbeInvalid);out.object["function_target_source"]=Value(functionTargetSource);out.object["function_thread_cpu_enabled"]=Value::flag(functionThreadCpu);out.object["function_thread_identity_mode"]=Value(std::string("tls_creation_once"));out.object["function_thread_identity_independent_of_cpu"]=Value::flag(true);out.object["function_thread_cpu_startup_read_mean_us"]=functionThreadCpu?Value(functionCpuReadMeanUs):Value();out.object["physics_back_thread_profiling"]=Value::flag(false);out.object["physics_thread_cpu_enabled"]=Value::flag(false);out.object["system_hook_count"]=Value((double)((profiling?1:0)+(navProfiling?1:0)+(functionProfiling?1:0)));out.object["nav_thread_cpu_enabled"]=Value::flag(navThreadCpu);out.object["nav_thread_cpu_startup_read_mean_us"]=navThreadCpu?Value(navCpuReadMeanUs):Value();out.object["paused"]=ready?Value::flag(world->isPaused()):Value();out.object["frame_speed_multiplier"]=ready?Value((double)world->getFrameSpeedMultiplier()):Value();SaveManager* saves=SaveManager::getSingleton();out.object["current_save"]=saves?Value(saves->getCurrentGame()):Value();out.object["save_signal"]=saves?Value((double)saves->signal):Value();out.object["save_root"]=saves?Value(saves->getSavePath()):Value();out.object["saved_origins_required"]=Value::flag(true);out.object["saved_origins_prepared"]=Value::flag(oracle::savedOrigins.prepared);out.object["saved_origins"]=oracle::savedOriginRegistrationState();}
    else if(cmd.str=="get_clock"){oracle::keys(p,0,0);out=oracle::clock(world);}
    else if(cmd.str=="dump_state"){const char* keys[]={"filename"};oracle::keys(p,keys,1);std::string filename=oracle::text(p,"filename",105);oracle::validateFilename(filename);out.object["_oracle_state"]=oracle::snapshot(world);out.object["_oracle_filename"]=Value(filename);out.object["_oracle_identity_source"]=oracle::savedOriginIdentitySource();}
    else if(cmd.str=="run_until")out=oracle::startRun(world,p);
    else if(cmd.str=="run_until_status")out=oracle::queryRun(world,p,false);
    else if(cmd.str=="cancel_run_until")out=oracle::queryRun(world,p,true);
    else if(cmd.str=="issue_order")out=oracle::issueOrder(world,p);
    else if(cmd.str=="resolve_saved_handles")out=oracle::resolveSavedHandles(world,p);
    else if(cmd.str=="begin_saved_origins")out=oracle::beginSavedOrigins(world,p);
    else if(cmd.str=="add_saved_origins")out=oracle::addSavedOrigins(world,p);
    else if(cmd.str=="commit_saved_origins")out=oracle::commitSavedOrigins(world,p);
    else if(cmd.str=="restore_scene_control")out=oracle::restoreControl(world,p);
    else if(cmd.str=="prepare_scene_control")out=oracle::prepareSceneControl(world,p);
    else if(cmd.str=="commit_scene_control")out=oracle::commitSceneControl(world,p);
    else if(cmd.str=="get_frame_stats"){StatisticsDetail detail=parseStatisticsDetail(p);out=stats((int)numeric(p,"n",1,3600,true),detail);}
    else if(cmd.str=="pause"){const Value& v=p.at("paused");if(v.type!=Value::BOOL)throw std::runtime_error("paused must be bool");if(!ready)throw std::runtime_error("world not ready");if(v.boolean){oracle::rememberSelectedSpeed(world,world->getFrameSpeedMultiplier(),"observed_running");oracle::stopRun(world,"cancelled");}world->userPause(v.boolean);out.object["paused"]=Value::flag(world->isPaused());}
    else if(cmd.str=="set_game_speed"){
        if(oracle::active())throw oracle::Error("busy","cancel run_until before changing speed");float speed=(float)numeric(p,"speed",0,5,false);bool preservePause=optionalFlag(p,"preserve_pause");
        if(preservePause&&speed==0)throw std::runtime_error("preserve_pause requires positive speed; use pause for zero");
        if(!ready)throw std::runtime_error("world not ready");
        bool wasPaused=world->isPaused();world->setGameSpeed(speed,false);
        // Both SDK calls finish in this command before originalLoop can advance time.
        if(preservePause)world->userPause(wasPaused);
        if(speed>0)oracle::rememberSelectedSpeed(world,speed);
        out.object["requested_speed"]=Value((double)speed);out.object["preserve_pause"]=Value::flag(preservePause);out.object["paused_before"]=Value::flag(wasPaused);
        out.object["frame_speed_multiplier"]=Value((double)world->getFrameSpeedMultiplier());out.object["paused"]=Value::flag(world->isPaused());
    }
    else if(cmd.str=="list_characters"){
        const Value& detail=p.at("details");bool details=detail.type==Value::BOOL&&detail.boolean;if(detail.type!=Value::NIL&&detail.type!=Value::BOOL)throw std::runtime_error("details must be bool");int limit=(int)numeric(p,"limit",1,details?100:500,true);if(!world->initialized||world->gameResetting||world->isLoadingFromASaveGame())throw std::runtime_error("world not ready");Value list=Value::arr();std::vector<Faction*> factionCandidates;
        const ogre_unordered_set<Character*>::type& chars=world->getCharacterUpdateList();
        for(ogre_unordered_set<Character*>::type::const_iterator i=chars.begin();i!=chars.end()&&(int)list.array.size()<limit;++i){Character* c=*i;if(!c)continue;Value row=Value::obj();row.object["name"]=Value(c->getName());Faction* f=c->getFaction();row.object["faction"]=f?Value(f->getName()):Value();Ogre::Vector3 pos=c->getPosition();Value xyz=Value::arr();xyz.array.push_back(Value(pos.x));xyz.array.push_back(Value(pos.y));xyz.array.push_back(Value(pos.z));row.object["position"]=xyz;if(details){GameData* gd=c->getGameData();if(gd&&gd->type==CHARACTER&&!c->isPlayerCharacter()&&f)factionCandidates.push_back(f);row.object["template_id"]=gd?Value(gd->stringID):Value();row.object["template_type"]=gd?Value((double)gd->type):Value();row.object["character_template"]=Value::flag(gd&&gd->type==CHARACTER);row.object["is_player"]=Value::flag(c->isPlayerCharacter());row.object["dead"]=Value::flag(c->isDead());row.object["unconscious"]=Value::flag(c->isUnconcious());float age=c->getAge();row.object["age"]=_finite(age)?Value(age):Value();}list.array.push_back(row);}out.object["characters"]=list;out.object["total_update_list"]=Value((double)chars.size());if(details)out.object["faction_relations"]=battle::factionInventory(factionCandidates);
    }
    else if(cmd.str=="get_scene_state"){if(!ready)throw std::runtime_error("world not ready");Value detail=p.object.count("thread_details")?p.at("thread_details"):Value();if(detail.type!=Value::NIL&&detail.type!=Value::BOOL)throw std::runtime_error("thread_details must be bool");out=sceneState(world,detail.type==Value::BOOL&&detail.boolean);}
    else if(cmd.str=="set_camera_free"){
        if(!ready)throw std::runtime_error("world not ready");if(!world->isPaused())throw std::runtime_error("pause the disposable test world before changing camera");const Value& enabled=p.at("enabled");if(enabled.type!=Value::BOOL)throw std::runtime_error("enabled must be bool");
        bool lock=optionalFlag(p,"lock_edge");bool release=optionalFlag(p,"release_edge");if(lock&&release)throw std::runtime_error("cannot lock and release camera together");if((lock||release)&&lastRequestedSave.empty())throw std::runtime_error("edge lock requires a save explicitly loaded through the probe");
        CameraClass* camera=sceneCamera(world);out.object["before"]=Value::flag(camera->isFreeCameraMode());if(camera->isFreeCameraMode()!=enabled.boolean)camera->setFreeCameraMode(enabled.boolean);if(lock)controlSceneCamera();if(release)restoreSceneCamera();out.object["edge_scrolling"]=::options?Value::flag(::options->edgeScrolling):Value();out.object["free_camera"]=Value::flag(camera->isFreeCameraMode());out.object["scene_camera_control_owned"]=Value::flag(sceneEdgeOwned);
    }
    else if(cmd.str=="list_towns"){
        if(!ready)throw std::runtime_error("world not ready");int limit=(int)numeric(p,"limit",1,500,true);const Value& filter=p.at("name_filter");if(filter.type!=Value::STRING||filter.str.size()>128)throw std::runtime_error("invalid town filter");
        lektor<RootObject*>& towns=townList()->getAllTowns();Value list=Value::arr();
        for(unsigned int i=0;i<towns.size()&&(int)list.array.size()<limit;++i){RootObject* town=towns[i];if(!town)continue;std::string name=town->getName();if(name.find(filter.str)==std::string::npos)continue;Value row=Value::obj();row.object["name"]=Value(name);row.object["position"]=vectorJSON(town->getPosition());Faction* faction=town->getFaction();row.object["faction"]=faction?Value(faction->getName()):Value();list.array.push_back(row);}
        out.object["towns"]=list;out.object["total_town_count"]=Value((double)towns.size());out.object["active_town_count"]=Value((double)townList()->getActiveTowns().size());
    }
    else if(cmd.str=="focus_town"){
        if(!ready)throw std::runtime_error("world not ready");if(!world->isPaused())throw std::runtime_error("pause the disposable test world before changing camera");const Value& name=p.at("name");if(name.type!=Value::STRING||name.str.empty()||name.str.size()>128)throw std::runtime_error("invalid town name");
        lektor<RootObject*>& towns=townList()->getAllTowns();RootObject* target=0;
        for(unsigned int i=0;i<towns.size();++i){if(towns[i]&&towns[i]->getName()==name.str){if(target)throw std::runtime_error("ambiguous town name");target=towns[i];}}
        if(!target)throw std::runtime_error("town not found");Ogre::Vector3 pos=target->getPosition();if(!_finite(pos.x)||!_finite(pos.y)||!_finite(pos.z))throw std::runtime_error("invalid town position");
        out.object["before"]=sceneState(world);CameraClass* camera=sceneCamera(world);camera->stopFollowing();camera->setFreeCameraMode(true);camera->teleport(pos);out.object["town"]=name;out.object["target_position"]=vectorJSON(pos);out.object["after"]=sceneState(world);
    }
    else if(cmd.str=="prepare_town_scene"){
        if(!ready||loadPending||lastRequestedSave!="KenshiProbe_test")throw std::runtime_error("load KenshiProbe_test through the probe before preparing a scene");
        if(!world->isPaused())throw std::runtime_error("pause the disposable test world before preparing a scene");
        const Value& name=p.at("name");if(name.type!=Value::STRING||name.str.empty()||name.str.size()>128)throw std::runtime_error("invalid town name");
        lektor<RootObject*>& towns=townList()->getAllTowns();RootObject* target=0;
        for(unsigned int i=0;i<towns.size();++i){if(towns[i]&&towns[i]->getName()==name.str){if(target)throw std::runtime_error("ambiguous town name");target=towns[i];}}
        if(!target)throw std::runtime_error("town not found");Ogre::Vector3 pos=target->getPosition();if(!_finite(pos.x)||!_finite(pos.y)||!_finite(pos.z))throw std::runtime_error("invalid town position");
        if(!world->player)throw std::runtime_error("player unavailable");const lektor<Character*>& players=world->player->getAllPlayerCharacters();
        if(!players.size()||players.size()>32)throw std::runtime_error("scene preparation requires 1..32 player characters");
        std::vector<Ogre::Vector3> destinations;Value moved=Value::arr();
        if(!players[0])throw std::runtime_error("player character unavailable");Ogre::Vector3 origin=players[0]->getPosition();
        for(unsigned int i=0;i<players.size();++i){Character* c=players[i];if(!c||!c->isPlayerCharacter()||!c->getMovement())throw std::runtime_error("player movement unavailable");Ogre::Vector3 old=c->getPosition();Ogre::Vector3 delta=old-origin;if(!_finite(delta.x)||!_finite(delta.y)||!_finite(delta.z)||delta.squaredLength()>1000000.0f)throw std::runtime_error("player formation is not local");Ogre::Vector3 dest=pos+delta;dest.y=pos.y;destinations.push_back(dest);Value row=Value::obj();row.object["name"]=Value(c->getName());row.object["before"]=vectorJSON(old);row.object["destination"]=vectorJSON(dest);moved.array.push_back(row);}
        CameraClass* camera=sceneCamera(world);out.object["before"]=sceneState(world);controlSceneCamera();
        for(unsigned int i=0;i<players.size();++i){CharMovement* movement=players[i]->getMovement();movement->halt();movement->_setPositionDirectionAndTeleport(destinations[i],Ogre::Quaternion(1,0,0,0));moved.array[i].object["after"]=vectorJSON(players[i]->getPosition());}
        camera->stopFollowing();camera->setFreeCameraMode(false);camera->teleport(pos);out.object["town"]=name;out.object["target_position"]=vectorJSON(pos);out.object["players"]=moved;out.object["after"]=sceneState(world);
    }
    else if(cmd.str=="prepare_battle_scene"){
        if(!ready||loadPending||lastRequestedSave!="KenshiProbe_test")throw std::runtime_error("load KenshiProbe_test through the probe before preparing a battle");
        if(!world->isPaused())throw std::runtime_error("pause the disposable test world before preparing a battle");
        const Value& sid=p.at("template_id");if(sid.type!=Value::STRING||sid.str.empty()||sid.str.size()>128)throw std::runtime_error("invalid template id");
        int pairs=(int)numeric(p,"pairs",1,20,true);const char* names[3]={"faction_name","opponent_template_id","opponent_faction_name"};std::string args[3];
        for(int i=0;i<3;++i){const Value& v=p.at(names[i]);if(v.type!=Value::NIL&&(v.type!=Value::STRING||v.str.size()>128||v.str.find('\0')!=std::string::npos))throw std::runtime_error("invalid optional faction/template name");if(v.type==Value::STRING)args[i]=v.str;}
        if(args[1].empty()&&!args[2].empty())throw std::runtime_error("opponent faction requires an opponent template");
        controlSceneCamera();out=battle::prepare(world,sid.str,pairs,args[0],args[1],args[2]);
    }
    else if(cmd.str=="save_scene_snapshot"){if(!ready)throw std::runtime_error("world not ready");const Value& name=p.at("name");if(name.type!=Value::STRING)throw std::runtime_error("snapshot name must be string");out=snapshots::create(world,name.str);}
    else if(cmd.str=="load_save"){
        const Value& name=p.at("name");
        if(name.type!=Value::STRING||name.str.empty()||name.str.size()>128||name.str=="."||name.str==".."||name.str.find_first_of("/\\:\r\n")!=std::string::npos||name.str.find('\0')!=std::string::npos)throw std::runtime_error("invalid save name");
        bool lock=optionalFlag(p,"lock_edge");bool explicitPause=p.object.count("pause_on_ready")?oracle::flag(p,"pause_on_ready"):false;
        SaveManager* saves=SaveManager::getSingleton();if(!saves)throw std::runtime_error("save manager unavailable");
        if(saves->signal|| (world&&world->gameResetting))throw std::runtime_error("save/load operation already pending");
        if(!saves->saveExists(saves->getSavePath(),name.str))throw std::runtime_error("save not found");
        oracle::stopRun(world,"cancelled");oracle::invalidateSelectedSpeed();oracle::invalidateSavedOrigins();restoreSceneCamera();if(lock)controlSceneCamera();battle::clear();bool tracking=snapshots::restoreTracking(name.str);bool pauseOnReady=explicitPause||tracking||name.str=="KenshiProbe_test";oracle::expectSavedOriginsLoad(name.str);saves->load(name.str);lastRequestedSave=name.str;loadPausePending=pauseOnReady;{Guard g;loadPending=true;}out.object["accepted"]=Value::flag(true);out.object["name"]=name;out.object["camera_edge_locked"]=Value::flag(lock);out.object["battle_tracking_restored"]=Value::flag(tracking);out.object["pause_on_ready"]=Value::flag(pauseOnReady);out.object["save_root"]=Value(saves->getSavePath());
    }
    else throw std::runtime_error("unknown command");
    Value response=Value::obj();response.object["id"]=r.at("id");response.object["result"].swap(out);return response;
}
static void pauseProtectedLoadWhenReady(GameWorld* world){
    if(!loadPausePending||!world||!world->initialized||world->gameResetting||world->isLoadingFromASaveGame())return;
    SaveManager* saves=SaveManager::getSingleton();if(!saves||saves->signal)return;
    world->userPause(true);loadPausePending=false;
}
static void drainCommands(GameWorld* world,bool menuService){
    // A bounded batch avoids a command flood taking over the game frame.
    for(int count=0;count<8;++count){boost::shared_ptr<Work> w;{Guard g;if(queue.empty())break;w=queue.front();queue.pop_front();if(w->cancelled)continue;if(menuService){const std::string& command=w->request.at("command").str;if(command!="ping"&&command!="load_save"){queue.push_front(w);break;}}}
        unsigned __int64 created=commandTimingEnabled?cachedThreadCreation(serviceIdentity,currentThreadCreation):0;
        double started=commandTimingEnabled?now():0;
        try{Value completed=execute(world,w->request);w->response.swap(completed);DebugLog("[KenshiOracle] command completed");}catch(const oracle::Error& e){w->response=error(w->request.at("id"),e.what(),e.code.c_str());DebugLog(std::string("[KenshiOracle] command error: ")+e.what());}catch(const std::exception& e){w->response=error(w->request.at("id"),e.what());DebugLog(std::string("[KenshiOracle] command error: ")+e.what());}catch(...){w->response=error(w->request.at("id"),"internal error");DebugLog("[KenshiOracle] internal command error");}
        double finished=commandTimingEnabled?now():0;
        if(commandTimingEnabled){try{attachServiceTiming(w->response,true,w->request.at("command").str,menuService,GetCurrentThreadId(),created,frame,w->queuedAt,started,finished);}catch(...){DebugLog("[KenshiOracle] service timing unavailable");}}
        SetEvent(w->done);
    }
}
static void loopHook(GameWorld* world,float dt){
    LARGE_INTEGER t;QueryPerformanceCounter(&t);++frame;
    Sample s;s.index=frame-1;s.ms=previous.QuadPart?1000.0*(t.QuadPart-previous.QuadPart)/frequency.QuadPart:0;
    {
        // Transfer the completed bucket and publish the new frame atomically.
        // A concurrent path completion must not be labelled with the next bucket.
        Guard g;s.mainAI=aiMain;aiMain=0;charsHistory.store(s.index,charsBucket);charsBucket.clear();s.functionCalls=functionBucket;functionBucket=CallBuckets();s.functionNested=functionNested;functionNested=0;
        s.navMs=navMs;s.navMax=navMax;s.navCalls=navCalls;s.navThreads=navThreads;
        navThreads=NavBuckets();navMs=navMax=0;navCalls=0;
        publishedFrame=frame;publishedTime=1000.0*t.QuadPart/frequency.QuadPart;gameThread=GetCurrentThreadId();
    }
    if(previous.QuadPart){samples.push_back(s);if(samples.size()>3600)samples.pop_front();}previous=t;
    pauseProtectedLoadWhenReady(world);try{oracle::tick(world);}catch(...){oracle::stopRun(world,"cancelled");DebugLog("[KenshiOracle] run_until stopped after clock error");}drainCommands(world,false);
    if(functionProfiling&&reusesMainServiceHook(functionTarget)){OriginalLoopInvocation<GameWorld> call={originalLoop,world,dt};profileFunction(call);}
    else originalLoop(world,dt);
}
static void rendererHook(Renderer* renderer){
        DWORD thread=GetCurrentThreadId();bool sameThread;
        {Guard g;++serviceFrame;serviceTime=now();serviceThread=thread;sameThread=!gameThread||thread==gameThread;}
        if(sameThread){oracle::synchronizeWorld(ou);if(oracle::active()&&(!ou||ou->gameResetting||ou->isLoadingFromASaveGame()))oracle::stopRun(ou,"cancelled");pauseProtectedLoadWhenReady(ou);drainCommands(ou,true);}
        if(sameThread&&ou&&ou->initialized&&!ou->gameResetting&&!ou->isLoadingFromASaveGame()){
            SaveManager* saves=SaveManager::getSingleton();if(saves&&!saves->signal&&!loadPausePending){Guard g;loadPending=false;}
        }
        if(functionProfiling&&reusesRendererServiceHook(functionTarget)){OriginalRendererInvocation<Renderer> call={originalRenderer,renderer};profileFunction(call);}
        else originalRenderer(renderer);
}
static bool sendAll(SOCKET c,const std::string& data){size_t off=0;while(off<data.size()){int n=send(c,data.data()+off,(int)(data.size()-off),0);if(n<=0)return false;off+=n;}return true;}
static DWORD WINAPI network(void*){
    WSADATA data;if(WSAStartup(MAKEWORD(2,2),&data))return 1;SOCKET server=socket(AF_INET,SOCK_STREAM,IPPROTO_TCP);if(server==INVALID_SOCKET){WSACleanup();return 1;}
    BOOL exclusive=TRUE;setsockopt(server,SOL_SOCKET,SO_EXCLUSIVEADDRUSE,(char*)&exclusive,sizeof(exclusive));
    char portText[16];DWORD len=GetEnvironmentVariableA("KENSHI_PROBE_PORT",portText,sizeof(portText));int port=47800;if(len&&len<sizeof(portText)){char* end=0;long v=strtol(portText,&end,10);if(*end||v<1||v>65535){DebugLog("[KenshiOracle] invalid port");closesocket(server);WSACleanup();return 1;}port=(int)v;}
    sockaddr_in addr={0};addr.sin_family=AF_INET;addr.sin_addr.s_addr=htonl(INADDR_LOOPBACK);addr.sin_port=htons((u_short)port);
    if(bind(server,(sockaddr*)&addr,sizeof(addr))||listen(server,8)){DebugLog("[KenshiOracle] bind/listen failed");closesocket(server);WSACleanup();return 1;}DebugLog("[KenshiOracle] listening on loopback");
    for(;;){SOCKET client=accept(server,0,0);if(client==INVALID_SOCKET)break;DWORD timeout=1000;setsockopt(client,SOL_SOCKET,SO_RCVTIMEO,(char*)&timeout,sizeof(timeout));setsockopt(client,SOL_SOCKET,SO_SNDTIMEO,(char*)&timeout,sizeof(timeout));std::string buffer;char bytes[2048];bool connected=true;
        while(connected){int n=recv(client,bytes,sizeof(bytes),0);if(n<=0)break;buffer.append(bytes,n);size_t newline;
            while((newline=buffer.find('\n'))!=std::string::npos){Value id;std::string line=buffer.substr(0,newline);buffer.erase(0,newline+1);Value reply;
                try{
                    if(line.size()>65535)throw std::runtime_error("line too long");
                    if(line.empty()||!MultiByteToWideChar(CP_UTF8,MB_ERR_INVALID_CHARS,line.data(),(int)line.size(),0,0))throw std::runtime_error("invalid UTF-8");
                    Value request=json::Parser(line).parse();id=request.at("id");
                    if(id.type!=Value::STRING||id.str.empty()||id.str.size()>64)throw std::runtime_error("id must be string, 1..64 bytes");
                    if(request.at("command").type!=Value::STRING||request.at("params").type!=Value::OBJECT)throw std::runtime_error("invalid command or params");
                    if(request.at("command").str=="heartbeat"){
                        // Only a copy of our own telemetry is read here, never game memory.
                        Value result=Value::obj();{Guard g;result.object["frame"]=Value((double)publishedFrame);result.object["timestamp_ms"]=Value(publishedTime);result.object["service_frame"]=Value((double)serviceFrame);result.object["service_timestamp_ms"]=Value(serviceTime);result.object["service_thread"]=Value((double)serviceThread);result.object["game_thread"]=Value((double)gameThread);result.object["loading"]=Value::flag(loadPending);}
                        reply=Value::obj();reply.object["id"]=id;reply.object["result"]=result;
                    }else{
                        boost::shared_ptr<Work> w(new Work(request));{Guard g;if(queue.size()>=64)throw std::runtime_error("queue full");if(commandTimingEnabled)w->queuedAt=now();queue.push_back(w);}
                        DWORD wait=WaitForSingleObject(w->done,9000);
                        if(wait!=WAIT_OBJECT_0){Guard g;w->cancelled=true;throw std::runtime_error("main thread timeout; execution may already have started");}
                        // Success event publishes the complete response. Service no
                        // longer accesses it; this shared_ptr keeps Work alive.
                        reply.swap(w->response);
                        if(reply.object.count("result")&&reply.at("result").object.count("_oracle_state")){Value& result=reply.object["result"];Value published=oracle::publishFile(result.at("_oracle_state"),result.at("_oracle_filename").str);if(result.object.count("_oracle_identity_source"))published.object["identity_source"]=result.at("_oracle_identity_source");result.swap(published);}
                    }
                }catch(const oracle::Error& e){reply=error(id,e.what(),e.code.c_str());}catch(const std::exception& e){reply=error(id,e.what());}catch(...){reply=error(id,"internal network error");}
                std::string wire=json::dump(reply)+"\n";if(wire.size()>65536)wire=json::dump(error(id,"response too large; reduce n or limit"))+"\n";if(!sendAll(client,wire)){connected=false;break;}
            }if(buffer.size()>65535){sendAll(client,json::dump(error(Value(),"line too long"))+"\n");break;}
        }closesocket(client);
    }closesocket(server);WSACleanup();return 0;
}
// C++ export name is required by RE_Kenshi; do not add extern "C".
__declspec(dllexport) void startPlugin(){
    char commandMode[4];commandTimingEnabled=GetEnvironmentVariableA("KENSHI_PROBE_COMMAND_TIMING",commandMode,sizeof(commandMode))==1&&commandMode[0]=='1';
    InitializeCriticalSection(&lock);QueryPerformanceFrequency(&frequency);previous.QuadPart=0;{std::ostringstream id;id.imbue(std::locale::classic());id<<GetCurrentProcessId()<<':'<<std::fixed<<std::setprecision(0)<<now();oracle::instanceId=id.str();}char cpuMode[4];navThreadCpu=GetEnvironmentVariableA("KENSHI_PROBE_NAV_THREAD_CPU",cpuMode,sizeof(cpuMode))==1&&cpuMode[0]=='1';if(navThreadCpu){double u=0,k=0,t=now();for(int i=0;i<200;++i)threadCpuMs(u,k);navCpuReadMeanUs=(now()-t)*1000.0/200;DebugLog("[KenshiOracle] optional navigation thread CPU enabled");}
    char targetMode[64];const char* targetEnv="KENSHI_PROBE_FUNCTION_TARGET";DWORD targetLength=GetEnvironmentVariableA(targetEnv,targetMode,sizeof(targetMode));
    if(!targetLength){targetEnv="KENSHI_PROBE_AI_TARGET";targetLength=GetEnvironmentVariableA(targetEnv,targetMode,sizeof(targetMode));}
    functionTargetSource=targetLength?targetEnv:"default";
    functionTarget=targetLength>=sizeof(targetMode)?FunctionProbeInvalid:parseFunctionProbeTarget(targetLength?std::string(targetMode):std::string());
    char functionCpuMode[4];DWORD cpuLength=GetEnvironmentVariableA("KENSHI_PROBE_FUNCTION_THREAD_CPU",functionCpuMode,sizeof(functionCpuMode));
    if(!cpuLength)cpuLength=GetEnvironmentVariableA("KENSHI_PROBE_AI_THREAD_CPU",functionCpuMode,sizeof(functionCpuMode));
    functionThreadCpu=cpuLength==1&&functionCpuMode[0]=='1';if(functionThreadCpu){double u=0,k=0,t=now();for(int i=0;i<200;++i)threadCpuMs(u,k);functionCpuReadMeanUs=(now()-t)*1000.0/200;}
    mainServiceInstalled=KenshiLib::AddHook(KenshiLib::GetRealAddress(&GameWorld::_NV_mainLoop_GPUSensitiveStuff),(void*)&loopHook,&originalLoop)==KenshiLib::SUCCESS;
    if(!mainServiceInstalled){DebugLog("[KenshiOracle] main hook failed");return;}
    // Three system hooks maximum: charsUpdate, ONE selected function and navigation.
    // Each selected SDK method has its exact prototype; physics is absent.
    bool a=KenshiLib::AddHook(KenshiLib::GetRealAddress(&GameWorld::charsUpdate),(void*)&charsHook,&originalChars)==KenshiLib::SUCCESS;
    profiling=a;intptr_t functionAddress=0;
    if(reusesServiceHook(functionTarget)){
        // Existing service detours only. Renderer success is known below.
        functionProfiling=reusesMainServiceHook(functionTarget)&&mainServiceInstalled;
    }else if(functionTarget==FunctionProbeCharsUT){
        functionAddress=KenshiLib::GetRealAddress(&GameWorld::charsUpdateUT);
        functionProfiling=functionAddress&&KenshiLib::AddHook(functionAddress,(void*)&charsUTHook,&originalCharsUT)==KenshiLib::SUCCESS;
    }else if(functionTarget==FunctionProbeZoneRendertime){
        functionAddress=KenshiLib::GetRealAddress(&ZoneManager::updateRendertimeThread);
        functionProfiling=functionAddress&&KenshiLib::AddHook(functionAddress,(void*)&zoneRendertimeHook,&originalZoneRendertime)==KenshiLib::SUCCESS;
    }else if(functionTarget==FunctionProbeMedicalPeriodic){
        functionAddress=KenshiLib::GetRealAddress(&MedicalSystem::_NV_periodicUpdate);
        functionProfiling=functionAddress&&KenshiLib::AddHook(functionAddress,(void*)&medicalPeriodicHook,&originalMedicalPeriodic)==KenshiLib::SUCCESS;
    }else if(functionTarget==FunctionProbeOgreRootFrame){
        rootFrameBinding=resolveLoadedModuleExport(L"OgreMain_x64.dll",rootFrameSymbol);
        functionAddress=(intptr_t)rootFrameBinding.address;
        functionProfiling=functionAddress&&KenshiLib::AddHook(functionAddress,(void*)&rootFrameHook,&originalRootFrame)==KenshiLib::SUCCESS;
    }else if(functionTarget==FunctionProbeHavokUpdate){
        functionAddress=KenshiLib::GetRealAddress(&HavokCharacter::update);
        functionProfiling=functionAddress&&KenshiLib::AddHook(functionAddress,(void*)&havokUpdateHook,&originalHavokUpdate)==KenshiLib::SUCCESS;
    }else{
        if(functionTarget==FunctionProbePeriodic)functionAddress=KenshiLib::GetRealAddress(&AI::_NV_periodicUpdate);
        else if(functionTarget==FunctionProbeFourFrame)functionAddress=KenshiLib::GetRealAddress(&AI::_NV_update4Frame);
        functionProfiling=functionAddress&&KenshiLib::AddHook(functionAddress,(void*)&aiFunctionHook,&originalAI)==KenshiLib::SUCCESS;
    }
    DebugLog(profiling?"[KenshiOracle] profiling hooks installed":"[KenshiOracle] profiling hooks incomplete");
    navProfiling=KenshiLib::AddHook(KenshiLib::GetRealAddress(&NavMesh::findPath),(void*)&pathHook,&originalPath)==KenshiLib::SUCCESS;
    DebugLog(navProfiling?"[KenshiOracle] NavMesh::findPath timing installed":"[KenshiOracle] NavMesh::findPath timing unavailable");
    bool menuOK=KenshiLib::AddHook(KenshiLib::GetRealAddress(&Renderer::_NV_update),(void*)&rendererHook,&originalRenderer)==KenshiLib::SUCCESS;
    rendererServiceInstalled=menuOK;
    if(reusesRendererServiceHook(functionTarget))functionProfiling=rendererServiceInstalled;
    DebugLog(std::string("[KenshiOracle] selected ")+functionProbeName(functionTarget)+(functionProfiling?" timing installed":" timing unavailable or invalid target"));
    DebugLog(menuOK?"[KenshiOracle] renderer service hook installed":"[KenshiOracle] renderer service hook unavailable");
    HANDLE thread=CreateThread(0,0,network,0,0,0);if(thread)CloseHandle(thread);else DebugLog("[KenshiOracle] network thread failed");
}

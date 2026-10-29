// SPDX-License-Identifier: GPL-3.0-only
#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#define _WIN32_WINNT 0x0601
#include <algorithm>
#include <stdexcept>
#include <iostream>
#include <limits>
#include <cstring>
#include "../plugin/OriginalLoopInvocation.h"
#include "../plugin/OriginalRendererInvocation.h"
#include "../plugin/OriginalBoolInvocation.h"
#include "../plugin/LoadedModuleExport.h"
#include "../plugin/PhysicsTelemetry.h"
#include "../plugin/AIProbeTarget.h"
#include "../plugin/FunctionProbeTarget.h"
#include "../plugin/CommandTiming.h"
static void require(bool ok){if(!ok)throw std::runtime_error("physics telemetry assertion");}
struct GroupedHex:std::numpunct<char>{char do_thousands_sep()const{return ',';}std::string do_grouping()const{return "\3";}};
struct MockWorld{int calls;float dt;MockWorld():calls(0),dt(0){}};
static void mockLoop(MockWorld* world,float dt){++world->calls;world->dt=dt;}
struct MockRenderer{int calls;MockRenderer():calls(0){}};
struct MockRoot{int calls;bool answer;MockRoot():calls(0),answer(false){}};
static MockRoot* expectedRoot=0;
static bool mockRootFrame(MockRoot* root){require(root==expectedRoot);++root->calls;return root->answer;}
static MockRenderer* expectedRenderer=0;
static void mockRenderer(MockRenderer* renderer){require(renderer==expectedRenderer);++renderer->calls;}
static void reconciles(const PhysicsBuckets& b){
    PhysicsTotals sum=b.overflow;for(int i=0;i<b.size;++i)sum.merge(b.threads[i].totals);
    require(sum.calls==b.total.calls&&sum.ms==b.total.ms&&sum.maximum==b.total.maximum);
    require(sum.cpuAvailable==b.total.cpuAvailable&&sum.userMs==b.total.userMs&&sum.kernelMs==b.total.kernelMs);
}
int main(){try{
    MockRoot root;expectedRoot=&root;for(int i=0;i<2;++i){root.answer=(i!=0);OriginalBoolInvocation<MockRoot> call={mockRootFrame,&root,!root.answer};call();require(root.calls==i+1&&call.result==root.answer);}
    require(parseFunctionProbeTarget("ogreRenderOneFrame")==FunctionProbeOgreRootFrame&&!reusesServiceHook(FunctionProbeOgreRootFrame)&&!isAIProbe(FunctionProbeOgreRootFrame));
    require(std::string(functionProbeName(FunctionProbeOgreRootFrame))=="Ogre::Root::renderOneFrame");
    LoadedModuleExport binding=resolveLoadedModuleExport(L"kernel32.dll","GetCurrentProcessId");require(binding.address&&!binding.modulePath.empty());
    std::locale originalLocale=std::locale();std::locale::global(std::locale(std::locale::classic(),new GroupedHex));
    LoadedModuleExport grouped=resolveLoadedModuleExport(L"kernel32.dll","GetCurrentProcessId");std::locale::global(originalLocale);
    require(grouped.address==binding.address&&grouped.addressHex==binding.addressHex&&grouped.addressHex.find(',')==std::string::npos&&grouped.addressHex.substr(0,2)=="0x");
    require(!resolveLoadedModuleExport(L"KenshiProbe_nonexistent_test.dll","Missing").address&&!resolveLoadedModuleExport(L"kernel32.dll","KenshiProbe_Missing_Export").address);
    require(!resolveLoadedModuleExport(0,"Missing").address&&!resolveLoadedModuleExport(L"kernel32.dll",0).address);
    wchar_t unicodePath[]={L'A',0x00e9,0xd83d,0xde80};std::string utf8;require(modulePathToUtf8(unicodePath,4,utf8)&&utf8=="A\xc3\xa9\xf0\x9f\x9a\x80");
    wchar_t invalidPath[]={0xd800};require(!modulePathToUtf8(invalidPath,1,utf8)&&utf8.empty());
    MockRenderer renderer,untouched;expectedRenderer=&renderer;OriginalRendererInvocation<MockRenderer> render={mockRenderer,&renderer};render();require(renderer.calls==1&&untouched.calls==0);
    require(parseFunctionProbeTarget("rendererUpdate")==FunctionProbeRendererUpdate);
    require(reusesRendererServiceHook(FunctionProbeRendererUpdate)&&reusesServiceHook(FunctionProbeRendererUpdate)&&!reusesMainServiceHook(FunctionProbeRendererUpdate)&&!isAIProbe(FunctionProbeRendererUpdate));
    require(reusesServiceHook(FunctionProbeMainLoopGPU)&&!reusesRendererServiceHook(FunctionProbeMainLoopGPU)&&!reusesServiceHook(FunctionProbeHavokUpdate));
    require(std::string(functionProbeName(FunctionProbeRendererUpdate))=="Renderer::update");
    MockWorld mock;float arguments[]={0.0f,-0.0f,1.0f,3.25f,1.0f/3.0f};
    for(int i=0;i<5;++i){OriginalLoopInvocation<MockWorld> call={mockLoop,&mock,arguments[i]};call();require(mock.calls==i+1&&std::memcmp(&mock.dt,&arguments[i],sizeof(float))==0);}
    require(parseFunctionProbeTarget("mainLoopGPUSensitive")==FunctionProbeMainLoopGPU);
    require(reusesMainServiceHook(FunctionProbeMainLoopGPU)&&!reusesMainServiceHook(FunctionProbeHavokUpdate)&&!isAIProbe(FunctionProbeMainLoopGPU));
    require(std::string(functionProbeName(FunctionProbeMainLoopGPU))=="GameWorld::mainLoop_GPUSensitiveStuff");
    json::Value response=json::Value::obj();response.object["result"]=json::Value::obj();
    require(!attachServiceTiming(response,false,"ping",false,7,134376698083790089ui64,12,100,105,107));
    require(!response.object["result"].object.count("_probe_service"));
    require(attachServiceTiming(response,true,"ping",false,7,134376698083790089ui64,12,100,105,107));
    json::Value timing=response.object["result"].at("_probe_service");
    require(timing.at("created_filetime").str=="134376698083790089"&&timing.at("queue_wait_ms").number==5&&timing.at("service_ms").number==2);
    require(timing.at("frame").number==12&&timing.at("identity_verified").boolean);
    require(!attachServiceTiming(response,true,"ping",false,7,1,12,105,100,107));
    require(!attachServiceTiming(response,true,"ping",false,0,1,12,100,105,107));
    require(!attachServiceTiming(response,true,"ping",false,7,1,12,-1,105,107));
    require(!attachServiceTiming(response,true,"ping",false,7,1,12,100,105,std::numeric_limits<double>::quiet_NaN()));
    require(!attachServiceTiming(response,true,"ping",false,7,1,12,100,105,std::numeric_limits<double>::infinity()));
    json::Value failure=json::Value::obj();failure.object["error"]=json::Value(std::string("test"));
    require(!attachServiceTiming(failure,true,"ping",false,7,1,12,100,105,107)&&!failure.object.count("result"));
    require(attachServiceTiming(response,true,"ping",true,7,0,12,100,105,107));
    require(response.object["result"].at("_probe_service").at("created_filetime").type==json::Value::NIL);
    require(parseAIProbeTarget("")==AIProbePeriodic&&parseAIProbeTarget("periodicUpdate")==AIProbePeriodic);
    require(parseAIProbeTarget("update4Frame")==AIProbeFourFrame);
    require(parseAIProbeTarget("typo")==AIProbeInvalid&&parseAIProbeTarget("UPDATE4FRAME")==AIProbeInvalid);
    require(std::string(aiProbeFunctionName(AIProbeFourFrame))=="AI::update4Frame");
    require(parseFunctionProbeTarget("")==FunctionProbePeriodic&&parseFunctionProbeTarget("periodicUpdate")==FunctionProbePeriodic);
    require(parseFunctionProbeTarget("update4Frame")==FunctionProbeFourFrame&&isAIProbe(FunctionProbeFourFrame));
    require(parseFunctionProbeTarget("charsUpdateUT")==FunctionProbeCharsUT&&!isAIProbe(FunctionProbeCharsUT));
    require(std::string(functionProbeName(FunctionProbeCharsUT))=="GameWorld::charsUpdateUT");
    require(parseFunctionProbeTarget("zoneRendertimeThread")==FunctionProbeZoneRendertime&&!isAIProbe(FunctionProbeZoneRendertime));
    require(std::string(functionProbeName(FunctionProbeZoneRendertime))=="ZoneManager::updateRendertimeThread");
    require(parseFunctionProbeTarget("medicalPeriodicUpdate")==FunctionProbeMedicalPeriodic&&!isAIProbe(FunctionProbeMedicalPeriodic));
    require(std::string(functionProbeName(FunctionProbeMedicalPeriodic))=="MedicalSystem::periodicUpdate");
    require(parseFunctionProbeTarget("havokCharacterUpdate")==FunctionProbeHavokUpdate&&!isAIProbe(FunctionProbeHavokUpdate));
    require(std::string(functionProbeName(FunctionProbeHavokUpdate))=="HavokCharacter::update");
    require(parseFunctionProbeTarget("CHARSUPDATEUT")==FunctionProbeInvalid&&parseFunctionProbeTarget("typo")==FunctionProbeInvalid);
    unsigned int depth=0;
    {CallDepthGuard outer(depth);require(outer.outermost&&depth==1);
        try{CallDepthGuard nested(depth);require(!nested.outermost&&depth==2);throw std::runtime_error("test unwind");}
        catch(const std::runtime_error&){require(depth==1);}}
    require(depth==0);
    PhysicsBuckets a;a.record(7,2,true,15.625,0);a.record(7,3,false,999,999);a.record(8,1,true,0,1);
    require(a.total.calls==3&&a.total.cpuAvailable==2&&a.total.userMs==15.625&&a.total.kernelMs==1);
    require(a.size==2&&a.total.maximum==3);reconciles(a);
    PhysicsBuckets b;for(int i=0;i<12;++i)b.record(100+i,1,true,1,2);
    require(b.size==8&&b.overflow.calls==4);reconciles(b);
    PhysicsBuckets c;c.record(100,5,true,3,4);c.merge(b);
    require(c.total.calls==13&&c.size==8&&c.threads[0].totals.calls==2);reconciles(c);
    PhysicsBuckets d;for(int i=0;i<8;++i)d.record(200+i,2,false,0,0);d.merge(b);
    require(d.total.calls==20&&d.overflow.calls==12&&d.total.cpuAvailable==12);reconciles(d);
    PhysicsBuckets frozen=d;d=PhysicsBuckets();require(d.total.calls==0&&frozen.total.calls==20);reconciles(frozen);
    PhysicsBuckets reused;reused.record(7,1,true,1,0,100);reused.record(7,1,true,1,0,200);
    require(reused.size==2&&reused.threads[0].creation!=reused.threads[1].creation);reconciles(reused);
    std::cout<<"Call bucket, historical physics and nested unwind checks passed (v100 x64)\n";return 0;
}catch(const std::exception& e){std::cerr<<e.what()<<"\n";return 1;}}

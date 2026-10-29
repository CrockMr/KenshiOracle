// SPDX-License-Identifier: GPL-3.0-only
#pragma once
// Uses only SDK ThreadClass identity fields. No name/running-state string reads,
// game mutations or retained SDK pointers. Borrowed handles are never closed.
struct ThreadQueryCopy {
    HANDLE value;
    ThreadQueryCopy():value(0){}
    ~ThreadQueryCopy(){if(value)CloseHandle(value);}
};
static Value sdkThreadRole(const char* role,ThreadClass* thread){
    Value row=Value::obj();row.object["role"]=Value(std::string(role));
    row.object["available"]=Value::flag(thread!=0);row.object["identity_verified"]=Value::flag(false);
    if(!thread)return row;
    // ThreadClass.h exposes threadID and threadHandle; no offsets are recoded.
    unsigned int expected=thread->threadID;HANDLE borrowed=(HANDLE)thread->threadHandle;
    row.object["sdk_thread_id"]=Value((double)expected);
    if(!expected||!borrowed){row.object["error"]=Value(std::string("SDK thread identity unavailable"));return row;}
    ThreadQueryCopy copy;
    if(!DuplicateHandle(GetCurrentProcess(),borrowed,GetCurrentProcess(),&copy.value,THREAD_QUERY_LIMITED_INFORMATION,FALSE,0)){
        DWORD error=GetLastError();row.object["winerror"]=Value((double)error);row.object["error"]=Value(std::string("Thread handle duplication failed"));return row;
    }
    DWORD tid=GetThreadId(copy.value),pid=GetProcessIdOfThread(copy.value);
    row.object["kernel_thread_id"]=Value((double)tid);row.object["kernel_process_id"]=Value((double)pid);
    if(!tid||tid!=expected||pid!=GetCurrentProcessId()){
        row.object["error"]=Value(std::string("SDK and kernel thread identities disagree"));return row;
    }
    FILETIME created,exited,kernel,user;
    if(!GetThreadTimes(copy.value,&created,&exited,&kernel,&user)){
        DWORD error=GetLastError();row.object["winerror"]=Value((double)error);row.object["error"]=Value(std::string("Thread creation query failed"));return row;
    }
    ULARGE_INTEGER stamp;stamp.LowPart=created.dwLowDateTime;stamp.HighPart=created.dwHighDateTime;
    std::ostringstream identity;identity.imbue(std::locale::classic());identity<<stamp.QuadPart;
    row.object["created_filetime"]=Value(identity.str());row.object["identity_verified"]=Value::flag(stamp.QuadPart!=0);
    return row;
}
static Value sdkThreadRoles(GameWorld* world){
    if(!world->isPaused())throw std::runtime_error("SDK thread details require a paused world");
    SaveManager* saves=SaveManager::getSingleton();
    if(!saves||saves->signal)throw std::runtime_error("SDK thread details unavailable during save/load");
    {Guard g;if(loadPending)throw std::runtime_error("SDK thread details unavailable during pending load");}
    Value out=Value::obj(),rows=Value::arr();
    rows.array.push_back(sdkThreadRole("world_ai_non_render",world->AINonRenderThread()));
    rows.array.push_back(sdkThreadRole("world_navmesh",world->navmesh));
    rows.array.push_back(sdkThreadRole("world_physics_interface",world->physics));
    rows.array.push_back(sdkThreadRole("physics_backthread",world->physics?world->physics->getBackthread():0));
    rows.array.push_back(sdkThreadRole("resource_loader",ResourceLoader::getInstance()));
    rows.array.push_back(sdkThreadRole("save_file_system",SaveFileSystem::getSingleton()));
    rows.array.push_back(sdkThreadRole("navmesh_generator",world->navmesh?world->navmesh->generator:0));
    out.object["process_id"]=Value((double)GetCurrentProcessId());out.object["frame"]=Value((double)frame);
    out.object["observed_qpc_ms"]=Value(now());out.object["roles"]=rows;
    return out;
}

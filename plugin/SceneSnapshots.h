// SPDX-License-Identifier: GPL-3.0-only
#pragma once

namespace snapshots {
struct Entry {std::string prefix;int requested,spawned;};
static std::map<std::string,Entry> entries;
static bool owns(const std::string& name){return entries.find(name)!=entries.end();}

static bool restoreTracking(const std::string& name){
    std::map<std::string,Entry>::const_iterator found=entries.find(name);if(found==entries.end())return false;
    battle::prefix=found->second.prefix;battle::requested=found->second.requested;battle::spawned=found->second.spawned;return true;
}

static Value create(GameWorld* world,const std::string& name){
    const std::string base="KenshiProbe_test_scene_";
    if(name.compare(0,base.size(),base)!=0||name.size()<=base.size()||name.size()>base.size()+40||name.find_first_not_of("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-")!=std::string::npos)throw std::runtime_error("invalid scene snapshot name");
    if(lastRequestedSave!="KenshiProbe_test"||loadPending||!world->isPaused()||battle::prefix.empty()||battle::spawned<1)throw std::runtime_error("a paused prepared battle on KenshiProbe_test is required");
    if(entries.size()>=8)throw std::runtime_error("snapshot limit reached for this plugin session");
    SaveManager* saves=SaveManager::getSingleton();if(!saves||saves->signal)throw std::runtime_error("save manager unavailable or busy");
    std::string root=saves->getSavePath();for(unsigned int i=0;i<root.size();++i)if((unsigned char)root[i]<32||(unsigned char)root[i]>127)throw std::runtime_error("safe scene snapshots require an ASCII save path");
    char absolute[MAX_PATH];DWORD n=GetFullPathNameA(root.c_str(),MAX_PATH,absolute,0);if(!n||n>=MAX_PATH)throw std::runtime_error("unsupported save path");root=absolute;
    DWORD attributes=GetFileAttributesA(root.c_str());if(attributes==INVALID_FILE_ATTRIBUTES||!(attributes&FILE_ATTRIBUTE_DIRECTORY))throw std::runtime_error("save directory unavailable");
    std::string target=root+"/"+name;attributes=GetFileAttributesA(target.c_str());
    if(attributes!=INVALID_FILE_ATTRIBUTES)throw std::runtime_error("scene snapshot target already exists; overwriting is forbidden");
    DWORD missing=GetLastError();if(missing!=ERROR_FILE_NOT_FOUND&&missing!=ERROR_PATH_NOT_FOUND)throw std::runtime_error("cannot verify scene snapshot target absence");
    Value out=Value::obj();out.object["battle_before"]=battle::state(world);
    Entry entry;entry.prefix=battle::prefix;entry.requested=battle::requested;entry.spawned=battle::spawned;
    // Saving can persist application settings. Restore the original edge option
    // before asking the engine to write its own new, disposable save directory.
    restoreSceneCamera();saves->save(name,false);entries[name]=entry;
    out.object["accepted"]=Value::flag(true);out.object["name"]=Value(name);out.object["save_root"]=Value(root);return out;
}
}

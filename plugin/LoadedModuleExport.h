// SPDX-License-Identifier: GPL-3.0-only
#pragma once
#include <windows.h>
#include <string>
#include <sstream>
#include <locale>

static bool modulePathToUtf8(const wchar_t* text,int length,std::string& result){
    result.clear();if(!text||length<=0)return false;
    int size=WideCharToMultiByte(CP_UTF8,WC_ERR_INVALID_CHARS,text,length,0,0,0,0);if(size<=0)return false;
    result.resize(size);
    if(WideCharToMultiByte(CP_UTF8,WC_ERR_INVALID_CHARS,text,length,&result[0],size,0,0)!=size){result.clear();return false;}
    return true;
}
struct LoadedModuleExport {
    void* address;
    std::string modulePath;
    std::string addressHex;
    LoadedModuleExport():address(0){}
};
static LoadedModuleExport resolveLoadedModuleExport(const wchar_t* moduleName,const char* symbol){
    LoadedModuleExport result;if(!moduleName||!*moduleName||!symbol||!*symbol)return result;
    HMODULE module=GetModuleHandleW(moduleName);if(!module)return result; // Never LoadLibrary here.
    FARPROC address=GetProcAddress(module,symbol);if(!address)return result;
    wchar_t path[2048];DWORD count=GetModuleFileNameW(module,path,2048);
    if(!count||count>=2048||!modulePathToUtf8(path,(int)count,result.modulePath))return result;
    std::ostringstream formatted;formatted.imbue(std::locale::classic());formatted<<"0x"<<std::hex<<(ULONG_PTR)address;
    result.addressHex=formatted.str();result.address=(void*)address;return result;
}

// SPDX-License-Identifier: GPL-3.0-only
// Offline minidump reader only. Never attaches, starts or controls a live target.
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <dbgeng.h>
#include <dbghelp.h>
#include <iostream>
#include <sstream>
#include <string>
#include <vector>

static std::string quote(const char* text){
    std::ostringstream out;out<<'"';
    for(const unsigned char* p=(const unsigned char*)text;*p;++p){
        if(*p=='"'||*p=='\\')out<<'\\'<<(char)*p;
        else if(*p<32)out<<'?';else out<<(char)*p;
    }out<<'"';return out.str();
}
static std::string hex64(ULONG64 n){std::ostringstream out;out<<"\"0x"<<std::hex<<n<<"\"";return out.str();}
int main(int argc,char** argv){
    if(argc!=4){std::cerr<<"dump_stacks dump_path local_symbol_path local_image_path\n";return 2;}
    if(strstr(argv[2],"://")||strchr(argv[2],';')||strchr(argv[2],'*'))return 2;
    wchar_t directory[MAX_PATH];if(!GetSystemDirectoryW(directory,MAX_PATH))return 3;
    std::wstring engine=std::wstring(directory)+L"\\dbgeng.dll";
    HMODULE module=LoadLibraryExW(engine.c_str(),0,0x800);if(!module)return 3;
    typedef HRESULT (WINAPI* Create)(REFIID,void**);
    Create create=(Create)GetProcAddress(module,"DebugCreate");
    IDebugClient* client=0;IDebugControl* control=0;IDebugSymbols* symbols=0;IDebugSystemObjects* system=0;
    HRESULT hr=create?create(__uuidof(IDebugClient),(void**)&client):E_FAIL;
    if(SUCCEEDED(hr))hr=client->QueryInterface(__uuidof(IDebugControl),(void**)&control);
    if(SUCCEEDED(hr))hr=client->QueryInterface(__uuidof(IDebugSymbols),(void**)&symbols);
    if(SUCCEEDED(hr))hr=client->QueryInterface(__uuidof(IDebugSystemObjects),(void**)&system);
    if(SUCCEEDED(hr))hr=symbols->SetSymbolOptions(SYMOPT_DEFERRED_LOADS|SYMOPT_IGNORE_NT_SYMPATH|SYMOPT_NO_PROMPTS|SYMOPT_FAIL_CRITICAL_ERRORS);
    if(SUCCEEDED(hr))hr=symbols->SetSymbolPath(argv[2]);
    if(SUCCEEDED(hr))hr=symbols->SetImagePath(argv[3]);
    if(SUCCEEDED(hr))hr=client->OpenDumpFile(argv[1]);
    if(SUCCEEDED(hr))hr=control->WaitForEvent(0,10000);
    std::cout<<"{\"open_hresult\":"<<hex64((ULONG)hr)<<",\"offline_only\":true,\"threads\":[";
    if(SUCCEEDED(hr)){
        ULONG count=0;hr=system->GetNumberThreads(&count);
        if(SUCCEEDED(hr)&&count>0&&count<=128){
            std::vector<ULONG> ids(count),tids(count);
            hr=system->GetThreadIdsByIndex(0,count,&ids[0],&tids[0]);
            if(SUCCEEDED(hr))for(ULONG i=0;i<count;++i){
                if(i)std::cout<<',';
                HRESULT threadStatus=system->SetCurrentThreadId(ids[i]);
                DEBUG_STACK_FRAME frames[64];ULONG filled=0;
                if(SUCCEEDED(threadStatus))threadStatus=control->GetStackTrace(0,0,0,frames,64,&filled);
                std::cout<<"{\"tid\":"<<tids[i]<<",\"debugger_thread_id\":"<<ids[i]
                    <<",\"stack_hresult\":"<<hex64((ULONG)threadStatus)<<",\"frame_limit\":64,\"frames\":[";
                for(ULONG j=0;j<filled;++j){
                    if(j)std::cout<<',';
                    ULONG mod=DEBUG_ANY_ID;ULONG64 base=0;
                    HRESULT modStatus=symbols->GetModuleByOffset(frames[j].InstructionOffset,0,&mod,&base);
                    char image[MAX_PATH]={0};
                    if(SUCCEEDED(modStatus))symbols->GetModuleNames(mod,base,image,MAX_PATH,0,0,0,0,0,0,0);
                    std::cout<<"{\"pc\":"<<hex64(frames[j].InstructionOffset)<<",\"return_address\":"<<hex64(frames[j].ReturnOffset)
                        <<",\"sp\":"<<hex64(frames[j].StackOffset)<<",\"module_base\":"<<hex64(base)
                        <<",\"image\":"<<quote(image)<<",\"module_hresult\":"<<hex64((ULONG)modStatus)<<'}';
                }std::cout<<"]}";
            }
        }else if(SUCCEEDED(hr))hr=E_FAIL;
    }
    std::cout<<"],\"result_hresult\":"<<hex64((ULONG)hr)<<"}\n";
    if(client)client->EndSession(DEBUG_END_PASSIVE);
    if(system)system->Release();if(symbols)symbols->Release();if(control)control->Release();if(client)client->Release();
    FreeLibrary(module);return SUCCEEDED(hr)?0:1;
}

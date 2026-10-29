// SPDX-License-Identifier: GPL-3.0-only
#pragma once
#include "OracleFormat.h"
#include <mygui/MyGUI_Gui.h>
#include <mygui/MyGUI_Button.h>
#include <mygui/MyGUI_Window.h>
#include <kenshi/GlobalConstants.h>
#include <windows.h>
#include <winver.h>
#include <cstring>
#include <set>
#pragma comment(lib,"MyGUIEngine_x64.lib")
#pragma comment(lib,"Version.lib")

// Read-only observation on the game/menu thread. No RE_Kenshi private function,
// variable, address or guessed layout is used. Widget contracts come from public
// RE_Kenshi v0.3.5 sources; the Python caller binds the loaded file to its hash.
// In particular, a false RNG checkbox does not prove that old detours vanished.
namespace rekenshi {
using json::Value;
inline void unavailable(const std::string& why){throw oracle::Error("rekenshi_settings_unavailable",why);}
inline void unverified(const std::string& why){throw oracle::Error("rekenshi_settings_unverified",why);}

struct FileHandle {
    HANDLE value;
    explicit FileHandle(HANDLE h):value(h){}
    ~FileHandle(){if(value!=INVALID_HANDLE_VALUE)CloseHandle(value);}
private: FileHandle(const FileHandle&);FileHandle& operator=(const FileHandle&);
};
inline std::wstring modulePath(HMODULE module){
    wchar_t path[32768];DWORD count=GetModuleFileNameW(module,path,32768);
    if(!count||count>=32768)unavailable("Cannot identify the loaded module file");
    return std::wstring(path,count);
}
inline std::string utf8(const std::wstring& text){
    if(text.empty())return std::string();
    int size=WideCharToMultiByte(CP_UTF8,WC_ERR_INVALID_CHARS,text.data(),(int)text.size(),0,0,0,0);
    if(size<=0)unavailable("Module path is not valid Unicode");
    std::string result(size,'\0');
    if(WideCharToMultiByte(CP_UTF8,WC_ERR_INVALID_CHARS,text.data(),(int)text.size(),&result[0],size,0,0)!=size)
        unavailable("Cannot encode module path");
    return result;
}
inline Value fileVersion(const std::wstring& path){
    DWORD ignored=0,size=GetFileVersionInfoSizeW(path.c_str(),&ignored);
    if(!size)return Value(); // Resource absence is not a version guess.
    if(size>1024*1024)unavailable("Module version resource exceeds the safety limit");
    std::vector<unsigned char> bytes(size);
    if(!GetFileVersionInfoW(path.c_str(),0,size,&bytes[0]))unavailable("Cannot read module file version");
    VS_FIXEDFILEINFO* info=0;UINT count=0;
    if(!VerQueryValueW(&bytes[0],L"\\",(void**)&info,&count)||!info||count<sizeof(VS_FIXEDFILEINFO)||info->dwSignature!=0xfeef04bd)
        unavailable("Invalid module version resource");
    std::ostringstream out;out.imbue(std::locale::classic());
    out<<HIWORD(info->dwFileVersionMS)<<'.'<<LOWORD(info->dwFileVersionMS)<<'.'
       <<HIWORD(info->dwFileVersionLS)<<'.'<<LOWORD(info->dwFileVersionLS);
    return Value(out.str());
}
inline std::string hexBytes(const unsigned char* bytes,size_t size){
    static const char* digits="0123456789abcdef";std::string result;result.reserve(size*2);
    for(size_t i=0;i<size;++i){result+=digits[bytes[i]>>4];result+=digits[bytes[i]&15];}return result;
}

// Bounded PE32+ reader for the actual loaded CRT's on-disk named exports. This
// parses public PE tables only and never maps or executes a second DLL image.
class DiskImage {
    std::vector<unsigned char> bytes;
    IMAGE_FILE_HEADER coff;
    IMAGE_OPTIONAL_HEADER64 optional;
    std::vector<IMAGE_SECTION_HEADER> sections;
    template<typename T> T read(size_t offset) const {
        if(offset>bytes.size()||sizeof(T)>bytes.size()-offset)unverified("Truncated module PE structure");
        T result;memcpy(&result,&bytes[offset],sizeof(T));return result;
    }
    std::string nameAt(DWORD rva) const {
        std::string name;
        for(unsigned int i=0;i<256;++i){
            if(rva>0xffffffffUL-i)unverified("Export name RVA overflows");
            unsigned char c=bytes[fileOffset(rva+i,1)];if(!c)return name;name+=(char)c;
        }unverified("Export name exceeds the safety limit");return name;
    }
public:
    explicit DiskImage(const std::wstring& path){
        FileHandle file(CreateFileW(path.c_str(),GENERIC_READ,FILE_SHARE_READ|FILE_SHARE_DELETE,0,OPEN_EXISTING,FILE_ATTRIBUTE_NORMAL,0));
        if(file.value==INVALID_HANDLE_VALUE)unavailable("Cannot open the loaded module file read-only");
        LARGE_INTEGER length;if(!GetFileSizeEx(file.value,&length)||length.QuadPart<64||length.QuadPart>64*1024*1024)
            unavailable("Module file size is unavailable or outside the safety limit");
        bytes.resize((size_t)length.QuadPart);DWORD received=0;
        if(!ReadFile(file.value,&bytes[0],(DWORD)bytes.size(),&received,0)||received!=bytes.size())
            unavailable("Cannot read the complete module file");
        IMAGE_DOS_HEADER dos=read<IMAGE_DOS_HEADER>(0);
        if(dos.e_magic!=IMAGE_DOS_SIGNATURE||dos.e_lfanew<0)unverified("Invalid module DOS header");
        size_t pe=(size_t)dos.e_lfanew;
        if(read<DWORD>(pe)!=IMAGE_NT_SIGNATURE)unverified("Invalid module PE signature");
        coff=read<IMAGE_FILE_HEADER>(pe+4);
        if(coff.Machine!=IMAGE_FILE_MACHINE_AMD64||coff.SizeOfOptionalHeader<sizeof(IMAGE_OPTIONAL_HEADER64)
           ||!coff.NumberOfSections||coff.NumberOfSections>96)unverified("Unsupported module PE layout");
        optional=read<IMAGE_OPTIONAL_HEADER64>(pe+4+sizeof(IMAGE_FILE_HEADER));
        if(optional.Magic!=IMAGE_NT_OPTIONAL_HDR64_MAGIC||optional.NumberOfRvaAndSizes<IMAGE_NUMBEROF_DIRECTORY_ENTRIES
           ||!optional.SizeOfImage||optional.SizeOfImage>1024*1024*1024)unverified("Invalid module optional header");
        size_t table=pe+4+sizeof(IMAGE_FILE_HEADER)+coff.SizeOfOptionalHeader;
        for(unsigned int i=0;i<coff.NumberOfSections;++i)sections.push_back(read<IMAGE_SECTION_HEADER>(table+i*sizeof(IMAGE_SECTION_HEADER)));
    }
    size_t fileOffset(DWORD rva,size_t count) const {
        size_t found=0,result=0;
        if(rva<optional.SizeOfHeaders&&count<=optional.SizeOfHeaders-rva&&rva<=bytes.size()&&count<=bytes.size()-rva){++found;result=rva;}
        for(size_t i=0;i<sections.size();++i){const IMAGE_SECTION_HEADER& s=sections[i];
            if(rva<s.VirtualAddress)continue;ULONGLONG delta=(ULONGLONG)rva-s.VirtualAddress;
            if(delta>s.SizeOfRawData||count>s.SizeOfRawData-delta)continue;
            ULONGLONG offset=(ULONGLONG)s.PointerToRawData+delta;
            if(offset>bytes.size()||count>bytes.size()-offset)unverified("Module section exceeds file bounds");
            ++found;result=(size_t)offset;
        }
        if(found!=1)unverified("Missing or ambiguous PE RVA mapping");return result;
    }
    DWORD exportedRva(const char* wanted) const {
        const IMAGE_DATA_DIRECTORY& table=optional.DataDirectory[IMAGE_DIRECTORY_ENTRY_EXPORT];
        if(!table.VirtualAddress||table.Size<sizeof(IMAGE_EXPORT_DIRECTORY))unverified("Module has no readable export directory");
        IMAGE_EXPORT_DIRECTORY exports=read<IMAGE_EXPORT_DIRECTORY>(fileOffset(table.VirtualAddress,sizeof(IMAGE_EXPORT_DIRECTORY)));
        if(exports.NumberOfNames>100000||exports.NumberOfFunctions>100000)unverified("Module export count exceeds the safety limit");
        size_t names=fileOffset(exports.AddressOfNames,(size_t)exports.NumberOfNames*4);
        size_t ordinals=fileOffset(exports.AddressOfNameOrdinals,(size_t)exports.NumberOfNames*2);
        size_t functions=fileOffset(exports.AddressOfFunctions,(size_t)exports.NumberOfFunctions*4);
        unsigned int matches=0;DWORD result=0;
        for(DWORD i=0;i<exports.NumberOfNames;++i){
            if(nameAt(read<DWORD>(names+(size_t)i*4))!=wanted)continue;
            WORD ordinal=read<WORD>(ordinals+(size_t)i*2);
            if(ordinal>=exports.NumberOfFunctions)unverified("Invalid named export ordinal");
            result=read<DWORD>(functions+(size_t)ordinal*4);++matches;
        }
        if(matches!=1||!result||result>=optional.SizeOfImage)unverified("CRT named export is missing or ambiguous");
        if(result>=table.VirtualAddress&&(ULONGLONG)result-table.VirtualAddress<table.Size)
            unverified("Forwarded CRT export cannot establish an unmodified entry");
        return result;
    }
    bool relocationOverlaps(DWORD rva,size_t count) const {
        const IMAGE_DATA_DIRECTORY& table=optional.DataDirectory[IMAGE_DIRECTORY_ENTRY_BASERELOC];
        if(!table.VirtualAddress&&!table.Size)return false;
        if(!table.VirtualAddress||table.Size>16*1024*1024)unverified("Invalid or excessive module relocation table");
        size_t offset=fileOffset(table.VirtualAddress,table.Size),used=0;
        while(used<table.Size){
            if(table.Size-used<sizeof(IMAGE_BASE_RELOCATION))unverified("Truncated relocation block");
            IMAGE_BASE_RELOCATION block=read<IMAGE_BASE_RELOCATION>(offset+used);
            if(block.SizeOfBlock<8||block.SizeOfBlock>table.Size-used||(block.SizeOfBlock-8)%2)
                unverified("Invalid relocation block size");
            for(DWORD at=8;at<block.SizeOfBlock;at+=2){
                WORD entry=read<WORD>(offset+used+at),kind=entry>>12;
                if(!kind)continue;
                ULONGLONG location=(ULONGLONG)block.VirtualAddress+(entry&0xfff);
                size_t width=kind==IMAGE_REL_BASED_DIR64?8:kind==IMAGE_REL_BASED_HIGHLOW?4:8;
                if(location<(ULONGLONG)rva+count&&(ULONGLONG)rva<location+width)return true;
            }
            used+=block.SizeOfBlock;
        }return false;
    }
    Value compareExport(HMODULE module,const char* name,bool& same) const {
        const size_t count=16;DWORD rva=exportedRva(name);
        FARPROC address=GetProcAddress(module,name);
        if(!address||(ULONG_PTR)address!=(ULONG_PTR)module+rva)unverified("Loaded CRT export differs from its file export table");
        if(rva>optional.SizeOfImage||count>optional.SizeOfImage-rva)unverified("CRT export prefix exceeds its image");
        if(relocationOverlaps(rva,count))unverified("A CRT export prefix contains relocations; comparison is inconclusive");
        size_t offset=fileOffset(rva,count);unsigned char memory[count];SIZE_T received=0;
        if(!ReadProcessMemory(GetCurrentProcess(),(LPCVOID)address,memory,count,&received)||received!=count)
            unavailable("Cannot read the loaded CRT export prefix");
        // Header identity prevents accepting a different disk build merely
        // because a symbol happened to move to the same RVA.
        IMAGE_DOS_HEADER loadedDos;IMAGE_NT_HEADERS64 loadedNt;
        if(!ReadProcessMemory(GetCurrentProcess(),module,&loadedDos,sizeof(loadedDos),&received)||received!=sizeof(loadedDos)
           ||loadedDos.e_magic!=IMAGE_DOS_SIGNATURE||loadedDos.e_lfanew<0||loadedDos.e_lfanew>1024*1024)
            unverified("Cannot validate loaded CRT image identity");
        if(!ReadProcessMemory(GetCurrentProcess(),(const unsigned char*)module+loadedDos.e_lfanew,&loadedNt,sizeof(loadedNt),&received)
           ||received!=sizeof(loadedNt)||loadedNt.Signature!=IMAGE_NT_SIGNATURE
           ||loadedNt.FileHeader.TimeDateStamp!=coff.TimeDateStamp||loadedNt.FileHeader.Machine!=coff.Machine
           ||loadedNt.OptionalHeader.SizeOfImage!=optional.SizeOfImage||loadedNt.OptionalHeader.CheckSum!=optional.CheckSum)
            unverified("Loaded CRT headers do not match the on-disk module");
        same=memcmp(memory,&bytes[offset],count)==0;Value row=Value::obj();
        row.object["symbol"]=Value(std::string(name));row.object["export_rva"]=Value((double)rva);
        row.object["disk_file_offset"]=Value((double)offset);row.object["checked_bytes"]=Value((double)count);
        row.object["disk_prefix_hex"]=Value(hexBytes(&bytes[offset],count));row.object["memory_prefix_hex"]=Value(hexBytes(memory,count));
        row.object["unmodified"]=Value::flag(same);row.object["relocation_overlap"]=Value::flag(false);
        row.object["comparison"]=Value(std::string(same?"identical":"different"));return row;
    }
};

inline void collectNamed(MyGUI::Widget* widget,const std::string& name,std::vector<MyGUI::Widget*>& matches,
                         std::set<MyGUI::Widget*>& visited,unsigned int depth){
    if(!widget||depth>64||visited.size()>=20000||!visited.insert(widget).second)
        unavailable("GUI widget hierarchy is missing, cyclic or exceeds the safety limit");
    if(widget->getName()==name)matches.push_back(widget);
    size_t children=widget->getChildCount();if(children>20000)unavailable("GUI child count exceeds the safety limit");
    for(size_t i=0;i<children;++i)collectNamed(widget->getChildAt(i),name,matches,visited,depth+1);
}
inline MyGUI::Widget* uniqueWidget(MyGUI::Widget* root,const char* name){
    std::vector<MyGUI::Widget*> matches;std::set<MyGUI::Widget*> visited;
    collectNamed(root,name,matches,visited,0);
    if(matches.size()!=1)unavailable(std::string("Expected exactly one RE_Kenshi widget: ")+name);
    return matches[0];
}
inline MyGUI::Widget* settingsRoot(){
    MyGUI::Gui* gui=MyGUI::Gui::getInstancePtr();if(!gui)unavailable("MyGUI has not initialized");
    std::vector<MyGUI::Widget*> matches;std::set<MyGUI::Widget*> visited;
    MyGUI::EnumeratorWidgetPtr roots=gui->getEnumerator();
    while(roots.next())collectNamed(roots.current(),"DebugWindow",matches,visited,0);
    if(matches.size()!=1||!matches[0]->castType<MyGUI::Window>(false))
        unavailable("RE_Kenshi settings window is absent, ambiguous or has the wrong type");
    return matches[0];
}
inline bool booleanWidget(MyGUI::Widget* root,const char* name){
    MyGUI::Button* button=uniqueWidget(root,name)->castType<MyGUI::Button>(false);
    if(!button)unavailable(std::string("RE_Kenshi setting is not a button: ")+name);
    return button->getStateSelected();
}
inline Value query(const std::string& instance){
    HMODULE module=GetModuleHandleW(L"RE_Kenshi.dll"),crt=GetModuleHandleW(L"MSVCR100.dll");
    if(!module||!crt)unavailable("RE_Kenshi or its already-loaded CRT is unavailable");
    MyGUI::Widget* root=settingsRoot();Value settings=Value::obj();
    const char* names[]={"FixRNG","UseCustomGameSpeeds","AttackSlotsOverride","MaxFactionSizeOverride","MaxSquadSizeOverride","MaxSquadsOverride"};
    const char* widgets[]={"FixRNGToggleEnableButton","UseCustomGameSpeedsEnableButton","AttackSlotsSlider_EnableButton",
                           "MaxFactionSizeSlider_EnableButton","MaxSquadSizeSlider_EnableButton","MaxSquadsSlider_EnableButton"};
    Value widgetNames=Value::obj();
    for(size_t i=0;i<6;++i){settings.object[names[i]]=Value::flag(booleanWidget(root,widgets[i]));widgetNames.object[names[i]]=Value(std::string(widgets[i]));}
    bool fix=settings.at("FixRNG").boolean;std::wstring crtPath=modulePath(crt),rekPath=modulePath(module);
    DiskImage disk(crtPath);bool randSame=false,srandSame=false;Value exports=Value::obj();
    exports.object["rand"]=disk.compareExport(crt,"rand",randSame);
    exports.object["srand"]=disk.compareExport(crt,"srand",srandSame);
    bool unchanged=randSame&&srandSame,changed=!randSame&&!srandSame;
    Value result=Value::obj();result.object["settings"]=settings;result.object["widgets"]=widgetNames;
    result.object["verification_method"]=Value(std::string("rekenshi_0_3_5_ui_and_crt_exports"));
    result.object["evidence_source"]=Value(std::string("runtime_ui"));result.object["process_id"]=Value((double)GetCurrentProcessId());
    result.object["instance_id"]=Value(instance);result.object["module_path"]=Value(utf8(rekPath));
    result.object["module_file_version"]=fileVersion(rekPath);result.object["crt_module_path"]=Value(utf8(crtPath));
    result.object["crt_exports"]=exports;result.object["crt_exports_unmodified"]=Value::flag(unchanged);
    result.object["crt_exports_modified"]=Value::flag(changed);
    result.object["runtime_settings_consistent"]=Value::flag((!fix&&unchanged)||(fix&&changed));
    result.object["effective_fix_rng_disabled"]=Value::flag(!fix&&unchanged);
    result.object["rng_hook_owner_verified"]=Value::flag(false); // Difference alone never identifies its author.
    result.object["startup_reseed_disabled"]=Value::flag(false); // RE_Kenshi 0.3.5 always seeds in MiscHooks::Init.
    Value constants=Value::obj();
    if(::con){constants.object["MAX_NUM_ATTACK_SLOTS"]=Value((double)::con->MAX_NUM_ATTACK_SLOTS);
        constants.object["MAX_FACTION_SIZE"]=Value((double)::con->MAX_FACTION_SIZE);
        constants.object["MAX_SQUAD_SIZE"]=Value((double)::con->MAX_SQUAD_SIZE);constants.object["MAX_SQUADS"]=Value((double)::con->MAX_SQUADS);}
    result.object["effective_constants"]=constants;return result;
}
} // namespace rekenshi

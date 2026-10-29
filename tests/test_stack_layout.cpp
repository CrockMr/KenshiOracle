// SPDX-License-Identifier: GPL-3.0-only
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <dbghelp.h>
#include <stddef.h>
#include <iostream>
int main(){
    std::cout<<"{\"address\":"<<sizeof(ADDRESS64)<<",\"kdhelp\":"<<sizeof(KDHELP64)
        <<",\"stackframe\":"<<sizeof(STACKFRAME64)<<",\"kdhelp_offset\":"<<offsetof(STACKFRAME64,KdHelp)
        <<",\"rsp_offset\":"<<offsetof(CONTEXT,Rsp)<<",\"rip_offset\":"<<offsetof(CONTEXT,Rip)
        <<",\"context_bytes\":"<<sizeof(CONTEXT)<<"}\n";
    return sizeof(STACKFRAME64)==264&&sizeof(CONTEXT)==1232?0:1;
}

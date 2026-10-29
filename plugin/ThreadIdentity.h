// SPDX-License-Identifier: GPL-3.0-only
#pragma once

// POD only: compatible with zero-initialized __declspec(thread) in v100.
// The caller must provide one state per OS thread, never a process-wide TID map.
// A failed first read stays unknown for that lifetime, without repeated syscalls.
struct ThreadIdentityState {
    unsigned int attempted;
    unsigned __int64 creation;
};
typedef bool (*ThreadCreationReader)(unsigned __int64&);
inline unsigned __int64 cachedThreadCreation(ThreadIdentityState& state,ThreadCreationReader read){
    if(!state.attempted){
        unsigned __int64 creation=0;
        state.attempted=1;
        state.creation=read(creation)&&creation?creation:0;
    }
    return state.creation;
}

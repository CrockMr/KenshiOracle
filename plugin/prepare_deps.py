"""Apply checked v100 compatibility fixes to the ignored official SDK checkout."""
from pathlib import Path
import os

default_sdk = Path(__file__).resolve().parent.parent/'references/KenshiLib_Examples_deps/KenshiLib'
sdk = Path(os.environ.get('KENSHILIB_DIR', str(default_sdk))).expanduser().resolve()
path = sdk/'Include/kenshi/NavMesh.h'
if not path.is_file():
    raise SystemExit('Set KENSHILIB_DIR to the KenshiLib dependency directory containing Include/kenshi/NavMesh.h')
source = path.read_text(encoding='utf-8')
old = 'MessageQueue<T>::Node*'
new = 'typename MessageQueue<T>::Node*'
if source.count(new) == 4:
    pass
elif source.count(old) == 4 and new not in source:
    path.write_text(source.replace(old, new), encoding='utf-8')
    print('NavMesh.h: added four required dependent-type typename keywords for v100')
else:
    raise SystemExit('Unexpected NavMesh.h revision; inspect dependency before applying the v100 fix')

# The official .lib exports hkArray<struct EdgePathNode,...>, whereas this
# dependency revision forward-declares it as class, changing MSVC mangling.
source = path.read_text(encoding='utf-8')
if source.count('class EdgePathNode;') == 1:
    path.write_text(source.replace('class EdgePathNode;', 'struct EdgePathNode;'), encoding='utf-8')
    print('NavMesh.h: matched EdgePathNode struct tag to the official import-library symbol')
elif source.count('struct EdgePathNode;') != 1:
    raise SystemExit('Unexpected EdgePathNode declaration; inspect SDK revision')

# AI.h incorrectly forward-declares CharacterMessage as a class. The SDK's
# Character.h defines the enum; include its declaration instead of inventing one.
ai_path = path.parent/'AI/AI.h'
source = ai_path.read_text(encoding='utf-8')
if source.count('class CharacterMessage;') == 1:
    ai_path.write_text(source.replace('class CharacterMessage;', '#include "../Character.h"'), encoding='utf-8')
    print('AI.h: use the CharacterMessage enum from Character.h')
elif source.count('#include "../Character.h"') != 1:
    raise SystemExit('Unexpected CharacterMessage declaration; inspect SDK revision')

# The official headers both define the same ParticlePool class. A shared guard
# keeps either header usable alone and leaves the class body/layout unchanged.
particle_headers = [path.parent/'ZoneManager.h', path.parent/'combat/CombatClass.h']
marker = 'class ParticlePool : public Ogre::GeneralAllocatedObject\n'
guard = 'KENSHI_PROBE_SDK_PARTICLE_POOL_DEFINED'
prefix = '#ifndef '+guard+'\n#define '+guard+'\n'
suffix = '\n#endif // '+guard
particle_sources = []
for header in particle_headers:
    text = header.read_text(encoding='utf-8')
    if text.count(marker) != 1:
        raise SystemExit('Unexpected ParticlePool definition; inspect SDK revision')
    start = text.index(marker)
    end = text.index('\n};', start)+4
    body = text[start:end]
    if guard in text:
        if (text.count(guard) != 3 or text[start-len(prefix):start] != prefix or
                text[end:end+len(suffix)] != suffix):
            raise SystemExit('Unexpected ParticlePool guard; inspect dependency before editing')
        guarded = True
    else:
        guarded = False
    particle_sources.append((header, text, start, end, body, guarded))
if particle_sources[0][4] != particle_sources[1][4]:
    raise SystemExit('ParticlePool definitions differ; refusing to merge SDK types')
for header, text, start, end, body, guarded in particle_sources:
    if not guarded:
        header.write_text(text[:start]+prefix+body+suffix+text[end:], encoding='utf-8')
        print(header.name+': guarded the identical ParticlePool definition without changing its body')

# Platoon.h and Building/Building.h duplicate this public enum. Including both
# is required to inspect loaded squads through the declared SDK API. Guard the
# identical declarations, preserving every name and value in each header.
enum_headers = [path.parent/'Platoon.h', path.parent/'Building/Building.h']
enum_marker = 'enum BuildingDesignation\n'
enum_guard = 'KENSHI_PROBE_SDK_BUILDING_DESIGNATION_DEFINED'
enum_prefix = '#ifndef '+enum_guard+'\n#define '+enum_guard+'\n'
enum_suffix = '\n#endif // '+enum_guard
enum_sources = []
for header in enum_headers:
    text = header.read_text(encoding='utf-8')
    if text.count(enum_marker) != 1:
        raise SystemExit('Unexpected BuildingDesignation declaration; inspect SDK revision')
    start = text.index(enum_marker)
    end = text.index('\n};', start)+4
    body = text[start:end]
    guarded = enum_guard in text
    if guarded and (text.count(enum_guard) != 3 or text[start-len(enum_prefix):start] != enum_prefix or text[end:end+len(enum_suffix)] != enum_suffix):
        raise SystemExit('Unexpected BuildingDesignation guard')
    enum_sources.append((header,text,start,end,body,guarded))
if enum_sources[0][4] != enum_sources[1][4]:
    raise SystemExit('BuildingDesignation declarations differ; refusing to merge SDK enums')
for header,text,start,end,body,guarded in enum_sources:
    if not guarded:
        header.write_text(text[:start]+enum_prefix+body+enum_suffix+text[end:], encoding='utf-8')
        print(header.name+': guarded the identical BuildingDesignation enum without changing its values')

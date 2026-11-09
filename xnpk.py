import sys
from npk import NovaPackage, NpkPartID
p = NovaPackage.load(sys.argv[1])
out = sys.argv[2]; n=0
def dump(parts, tag):
    global n
    for part in parts:
        print(tag, part.id.name, len(part.data) if isinstance(part.data,bytes) else 'obj')
        if part.id == NpkPartID.SQUASHFS and isinstance(part.data,bytes):
            open(f"{out}/sq{n}.sfs",'wb').write(part.data); n+=1
dump(p._parts,'top')
for i,pkg in enumerate(p._packages): dump(pkg, f'pkg{i}')
print("squashfs:", n)

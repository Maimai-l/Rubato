"""检查音源资产是否就位。缺失不报错退出(除非连 S1 都没有),而是打印清晰的手动获取指引。"""
import pathlib
import sys
import yaml

ROOT = pathlib.Path(__file__).parents[1]
cfg = yaml.safe_load((ROOT / "configs/sources.yaml").read_text())

HINTS = {
    "S1_salamander": "github.com/sfzinstruments/SalamanderGrandPiano (CC-BY 3.0)。解压到 assets/soundfonts/SalamanderGrandPiano/",
    "S2_splendid": "github.com/sfzinstruments/SplendidGrandPiano (Public Domain)。解压到 assets/soundfonts/SplendidGrandPiano/",
    "S3_experience_ny": "The Experience NY S&S Model B V1.0.zip → 解压到 assets/soundfonts/TheExperienceNY/",
    "S4_kamoepiano": "kamoepiano301.zip → 解压到 assets/soundfonts/Kamoepiano/",
}

present, missing = [], []
for sid, s in cfg["sources"].items():
    p = ROOT / s["path"]
    (present if p.exists() else missing).append(sid)

print(f"音源就位: {present or '无'}")
if missing:
    print(f"\n缺失 {len(missing)} 个音源,手动获取指引:")
    for sid in missing:
        print(f"  [{sid}]  {HINTS.get(sid, '见 configs/sources.yaml 的 url 字段')}")
    print("\n注:S1(Salamander)是主力(40% 渲染量),必须补齐。S2-S4 缺失可降级(权重会重新归一)。")

# IR:合成的不需要文件;检查是否有用户放的真实 IR 覆盖
real_ir = list((ROOT / "assets/irs/real").glob("*.wav")) if (ROOT / "assets/irs/real").exists() else []
print(f"\n真实 IR 覆盖: {len(real_ir)} 个(0 个=全部用程序化合成 IR,正常)")

if "S1_salamander" in missing:
    print("\n!!! S1 主力音源缺失,渲染无法进行。补齐后重跑。 !!!")
    sys.exit(1)
print("\n资产检查通过(或仅缺可降级音源)。")

# Roof Generator — Blender addon

[English](README.md) | 日本語

平面の建物footprintから、一体の編集可能なBlender屋根メッシュを生成します。
凹形状・非直交形状、長方形・平行四辺形・台形・一般的な凸四辺形に対応します。
L/T/U型は複数のRoofPartを接続して生成します。屋根種別は
**flat・gable・hip・shed**で、棟・隅棟・谷は屋根面の交線から決まります。
屋根計算では、直線からの折れが5度以内（凸側の内角175度以上、凹側185度以下）の
連続辺を一本に統合します。中間点を除いた両端を結ぶため、屋根の輪郭は少し変わります。
元の入力メッシュは変更しません。直角の角は残ります。

## インストールと使い方

1. [`roof_generator-1.0.0.zip`](packages/roof_generator-1.0.0.zip) を **Download raw file** で保存します。
2. Blender 4.3以降の **Edit → Preferences → Add-ons → Install from Disk** でZIPを選び、**Roof Generator**を有効にします。
3. Shapelyのセットアップが必要な場合、addon設定の **Install Shapely (Internet)** を押します。pipを使えるホストPythonが必要です。自動検出できなければ **Host Python with pip** に実行ファイルを指定します。
4. Object Modeで、面が張られた平面footprintメッシュを選択します。
5. 3D Viewのサイドバー（**N**）→ **Roof** で屋根種別・勾配・軒高offsetを設定し、**Generate roof** を押します。

変換はUndoに対応し、入力オブジェクトを保持します。**Hide source footprint**で
入力の表示を切り替えられます。出力はUVレイヤー・マテリアル・part/crease属性を持つ
通常のメッシュで、編集やUV展開ができます。回転・移動・非一様scaleに対応し、
transformのApplyは不要です。

生成するのは外周境界を持つ屋根表面です。建物の壁や屋根の厚みは別途モデリングします。
穴付き・自己交差・非平面のfootprint、分解探索の上限超過、対応範囲外の垂直段差接続は、
明示的なエラーになります。

## ベースメッシュの大量生成

サイドバー（**N**）→ **Building** → **Create Base Meshes** から個数と寸法を
指定します。各オブジェクトは **Building Base · 1m** のGeometry Nodesを持ち、
モディファイアの **Width / Depth / Max Cut / Step Length / Minimum Span / Seed / Height**
を変更すると即座に更新されます。各個体のSeedは連番です。

1m四方の面からなる平面メッシュの外周を、ランダムな段状に削ります。
中央の帯を残して、穴と分断を防ぎます。この方式では各行が中央の帯につながる
形に限定されます。**Max Cut = 0** なら長方形です。1 Blender unit = 1m、
オブジェクトscale = 1を前提とします。屋根以外の生成にも使える通常の平面形状で、
編集モードで加工するときはモディファイアをApplyします。
RoofをOFFにしたベース生成にはShapelyもpipも不要です。

**Height = 0** なら平面、0より大きければ指定した高さまで壁を押し出し、底面も
閉じた立体になります。小数の高さも指定できます。ノードグループの **Roof Base**
出力からは、その高さの上面だけを平面メッシュとして取り出せます。
**Roof** をONにすると、既存の屋根生成と同じ分割・棟・谷の仕様で屋根を生成します。
**Roof Type** はFlat/Gable/Hip/Shed、**Roof Pitch** は勾配です。
Heightが正なら壁・底面と屋根をつないだ閉じた建物、0なら屋根表面になります。
**Roof Surface** 出力から屋根だけを取り出せます。

屋根ONには現在の屋根計算と同じShapelyが必要です。寸法・Seed・種別・勾配の変更時は、
有効なaddonが既存のPython屋根計算を実行して結果を更新します。HeightとRoofの切替は
Geometry Nodes内で反映され、同じ形状の屋根を再計算しません。
屋根計算自体の速度や対応範囲は既存生成と同じです。未対応の接続ではBuildingパネルに
エラーを表示し、古い屋根は表示しません。更新待ち・失敗時も現在のベースと壁は表示します。
既存の屋根付きサンプルも、addonを有効にして開くとこの表示に更新されます。
依存関係を導入した後などは **Retry Roof** で再試行できます。

## ライセンス

| 対象 | ライセンスと条件 |
| --- | --- |
| Roof Generatorのソース・ツール・テスト | **GPL-3.0-or-later**。GPLの条件下で商用利用可能です。配布時はライセンスとソース提供に関する条件を満たす必要があります。 |
| 実行時の依存ライブラリ | NumPy・Shapely: BSD-3-Clause、GEOS: LGPL-2.1。 |

ファイルごとの適用範囲・出典・ライセンス全文は [LICENSING.md](LICENSING.md)、
依存ライブラリの条件は [Third-party notices](addon/roof_generator/THIRD_PARTY_NOTICES.md) を参照してください。

## リポジトリ構成

| 場所 | 役割 |
| --- | --- |
| [`addon/roof_generator/`](addon/roof_generator/) | Blender UI・footprint geometry・メッシュ出力 |
| [`packages/`](packages/) | インストール用addon ZIP |
| [`python/`](python/README.md) | build・tests・footprint CLI |
| [`python/docs/`](python/docs/) | generator設計・先行研究との比較 |
| [`reference/`](reference/README.md) | ソース・研究への参照 |
| `python/out/`、`dist/` | 検証結果・buildの生成物 |

## 開発と検証

```bash
python -m pip install -r python/requirements.txt
python -m unittest discover -s python/tests
python python/build_addon.py
blender -b --factory-startup --python-exit-code 1 --python python/blender_smoke_test_addon.py -- --zip dist/roof_generator-1.0.0.zip
```

検証対象は11件のacceptanceテスト、最終メッシュまで生成する16ケース、4種別の屋根、
UV・マテリアル編集、transform、失敗時のscene不変、addonの登録処理です。
L/T/U・非直交・住宅形状の代表ケースは、レンダリングでも確認しています。
CIはWindows/LinuxのPython 3.11/3.13でcoreテストとZIPの一致確認を行い、
LinuxのBlender 4.3.2でインストール済みaddonとfootprint CLIを検証します。
Blenderの実行検証環境は現在Linuxです。

詳細は [generator設計](python/docs/ROOF_GENERATOR_DESIGN.md) と
[Pythonガイド](python/README.md) を参照してください。

# Roof Generator — Blender addon

[English](README.md) | 日本語

平面の建物footprintから、一体の編集可能なBlender屋根メッシュを生成します。
凹形状・非直交形状、長方形・平行四辺形・台形・一般的な凸四辺形に対応します。
L/T/U型は複数のRoofPartを接続して生成します。屋根種別は
**flat・gable・hip・shed**で、棟・隅棟・谷は屋根面の交線から決まります。

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

## ライセンス

| 対象 | ライセンスと条件 |
| --- | --- |
| Blender addon・footprint geometry | **GPL-3.0-or-later**。GPLの条件下で商用利用可能です。配布時はライセンスとソース提供に関する条件を満たす必要があります。 |
| SGA21由来のPython研究用移植コード | **CC BY-NC 4.0**。非商用利用限定です。出典・ライセンスへのリンク・変更した旨の表示が必要です。 |
| 実行時の依存ライブラリ | NumPy・Shapely: BSD-3-Clause、GEOS: LGPL-2.1。 |

ファイルごとの適用範囲・出典・ライセンス全文は [LICENSING.md](LICENSING.md)、
依存ライブラリの条件は [Third-party notices](addon/roof_generator/THIRD_PARTY_NOTICES.md) を参照してください。

## リポジトリ構成

| 場所 | 役割 |
| --- | --- |
| [`addon/roof_generator/`](addon/roof_generator/) | Blender UI・footprint geometry・メッシュ出力 |
| [`packages/`](packages/) | インストール用addon ZIP |
| [`python/`](python/README.md) | build・tests・CLI・SGA21研究用移植コード |
| [`python/docs/`](python/docs/) | generator設計・論文との対応関係 |
| [`reference/`](reference/README.md) | ソース・研究への参照 |
| `python/out/`、`dist/` | 検証結果・buildの生成物 |

## 開発と検証

```bash
python -m pip install -r python/requirements.txt
python -m unittest python.tests.test_roof_core python.tests.test_roof_acceptance
python python/build_addon.py
blender -b --factory-startup --python-exit-code 1 --python python/blender_smoke_test_addon.py -- --zip dist/roof_generator-1.0.0.zip
```

検証対象は90件のテスト、最終メッシュまで生成する16ケース、4種別の屋根、
UV・マテリアル編集、transform、失敗時のscene不変、addonの登録処理です。
L/T/U・非直交・住宅形状の代表ケースは、レンダリングでも確認しています。
CIはWindows/LinuxのPython 3.11/3.13でcoreテストとZIPの一致確認を行い、
LinuxのBlender 4.3.2でインストール済みaddonを検証します。
Blenderの実行検証環境は現在Linuxです。

詳細は [generator設計](python/docs/ROOF_GENERATOR_DESIGN.md) と
[Pythonガイド](python/README.md) を参照してください。

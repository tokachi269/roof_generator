# Roof Generator — Blender addon

[English](README.md) | 日本語

平面の建物footprintから、一体の編集可能なBlender屋根メッシュを生成します。
凹形状・非直交形状、長方形・平行四辺形・台形・一般的な凸四辺形に対応します。
L/T/U型は複数のRoofPartを接続して生成します。屋根種別は
**flat・gable・hip・shed**で、棟・隅棟・谷は屋根面の交線から決まります。

## インストールと使い方

1. [`roof_generator-1.1.0.zip`](packages/roof_generator-1.1.0.zip) を **Download raw file** で保存します。
2. Blender 4.3以降の **Edit → Preferences → Add-ons → Install from Disk** でZIPを選び、**Roof Generator**を有効にします。
3. Shapelyのセットアップが必要な場合、addon設定の **Install Shapely (Internet)** を押します。pipを使えるホストPythonが必要です。自動検出できなければ **Host Python with pip** に実行ファイルを指定します。
4. Object Modeで、面が張られた平面footprintメッシュを1つ以上選択します。
5. 3D Viewのサイドバー（**N**）→ **Roof** で屋根種別・勾配・軒高offsetを設定し、**Generate roofs** を押します。

選択したfootprintごとに1つの屋根objectを生成します。複数入力はまとめて評価し、
対応外の入力があればsceneを変更する前にbatch全体を失敗させます。
変換はUndoに対応し、入力オブジェクトを保持します。**Hide source footprint**で
入力の表示を切り替えられます。出力はUVレイヤー・マテリアル・part/crease属性を持つ
通常のメッシュで、編集やUV展開ができます。回転・移動・非一様scaleに対応し、
transformのApplyは不要です。

生成するのは外周境界を持つ屋根表面です。建物の壁や屋根の厚みは別途モデリングします。
穴付き・自己交差・非平面のfootprint、分解探索の上限超過、対応範囲外の垂直段差接続は、
明示的なエラーになります。

## 生成方式と速度

境界の頂点列とcutでRoofPartを選び、支持線の拘束から2D RoofGraphを作り、
そのface cycleを3Dへ埋め込みます。共通の勾配・軒高の変更ではgraphを再利用します。
平面性・面の被覆・manifoldの検証は毎回実行します。
初回・再生成・Blenderでの1,000棟の実測は [performance measurements](python/docs/ROOF_PERFORMANCE.md) を参照してください。

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
blender -b --factory-startup --python-exit-code 1 --python python/blender_smoke_test_addon.py -- --zip dist/roof_generator-1.1.0.zip
```

検証対象は30件のテスト、最終メッシュまで生成する16ケース、4種別の屋根、
UV・マテリアル編集、transform、失敗時のscene不変、addonの登録処理です。
L/T/U・非直交・住宅形状の代表ケースは、レンダリングでも確認しています。
CIはWindows/LinuxのPython 3.11/3.13でcoreテストとZIPの一致確認を行い、
LinuxのBlender 4.3.2でインストール済みaddonとfootprint CLIを検証します。
Blenderの実行検証環境は現在Linuxです。

詳細は [generator設計](python/docs/ROOF_GENERATOR_DESIGN.md) と
[Pythonガイド](python/README.md) を参照してください。

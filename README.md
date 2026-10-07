# Roof Generator — Blender addon

平面footprintを選択し、**変換ボタンで一体の編集可能な屋根meshを生成**するaddonです。
concave・非直交形状、rectangle / parallelogram / trapezoid / convex quad、
L/T/Uの複数part接続、flat / gable / hip / shedに対応します。
棟・隅棟・谷はroof planeの交線から決まり、出力は通常のBlender meshです。

## インストールと変換

1. [`packages/roof_generator-1.0.0.zip`](packages/roof_generator-1.0.0.zip) をDownload raw fileで保存します。
2. Blender 4.3以降の **Edit → Preferences → Add-ons → Install from Disk** でZIPをインストールし、Roof Generatorを有効にします。
3. 依存がない場合、addon設定の **Install Shapely (Internet)** を押します。pipを使えるホストPythonが必要です。自動検出できなければ **Host Python with pip** に実行ファイルを指定します。
4. Object Modeで、面が張られた平面footprint meshを選択します。
5. 3D Viewのサイドバー（Nキー）→ **Roof** で種別・勾配・軒高offsetを設定し、**Generate roof** を押します。

変換はUndo対応です。入力は保持し、Hide source footprintで表示を切り替えられます。
屋根のUVレイヤー・マテリアル・part/crease属性を生成し、通常のUV展開やmesh編集ができます。
回転・移動・非一様scaleのApplyは不要です。出力は外周境界を持つ屋根表面で、壁や厚みは別です。
実装した入口は変換ボタンです。Geometry Nodesによるライブ生成modifierは提供していません。

ZIPはaddonソースだけを含み、元データやSGA21移植コード、OS別バイナリを含みません。
依存のインストールは明示的にボタンを押した時だけ行います。Windows/LinuxのCPythonに合う
Shapely wheelを取得し、付属のライセンスファイルも保持します。

## 構成と権利

| 場所 | 役割・ライセンス |
| --- | --- |
| [`addon/roof_generator/`](addon/roof_generator/) | 新規実装のgeometry・Blender addon。GPL-3.0-or-later |
| [`packages/`](packages/) | ソースと同期したインストール用ZIP |
| [`python/`](python/README.md) | build、tests、CLI、SGA21由来の非商用research port |
| [`python/docs/`](python/docs/) | 設計・先行研究・移植の対応関係 |
| [`reference/README.md`](reference/README.md) | 元リポジトリ・論文への外部参照のみ |
| `python/out/`、`dist/` | 検証結果・build出力（Git管理対象外） |

**元のMATLAB・UI・dataset・旧utilityファイルとコピーfixtureは削除済み**です。
履歴はtokachi269のnoreply表記による独立したrootから構成しています。履歴の変更によって、
SGA21由来の移植部分の権利条件が消えるわけではありません。

[LICENSING.md](LICENSING.md) がファイル別の権利範囲を定義します。
**addonの新規実装はGPL、SGA21由来のresearch portはCC BY-NC 4.0を維持**しています。
商用利用・再ライセンスについてSGA21著者の別途許可は取得していません。
addon ZIPはそのresearch portを含まず、依存もしません。新規addonと移植部分を
一括してMIT/GPL扱いにはしていません。

## 検証・開発

```bash
python -m pip install -r python/requirements.txt
python -m unittest python.tests.test_roof_core python.tests.test_roof_acceptance
python python/build_addon.py
blender -b --factory-startup --python-exit-code 1 --python python/blender_smoke_test_addon.py -- --zip dist/roof_generator-1.0.0.zip
```

90件の自動テストと、ZIPを実際にインストールしたBlenderで16必須ケース・4種別・
UV/material・transform・unsupported時のscene不変・登録解除/再登録を確認しています。
実行検証はLinuxのBlender 4.3.2です。WindowsのBlender実行は未検証です。
詳細は [設計書](python/docs/ROOF_GENERATOR_DESIGN.md) と [Python手順](python/README.md) を参照してください。

穴付きfootprint、自己交差、非平面入力、探索上限超過、未設計の垂直段差接続などは
unsupportedとして失敗します。壊れたmeshへのfallbackは行いません。

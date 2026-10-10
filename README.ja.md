# Roof Generator — Blender addon

[English](README.md) | 日本語

Blender 4.3以降で、面を張った平面footprintから編集可能な屋根表面を生成します。
直交gableはregionから外周の端状態を解釈し、polygon全体の一体構造からRoofGraphを作ります。
数学的な矩形分割の境界は独立した屋根にはしません。
同等に妥当な候補はgeneration seedで選び、未対応のtopologyは明示的なエラーにします。

## 現在の対応範囲

| 入力・屋根 | 出力 |
| --- | --- |
| 長方形（回転・正方形を含む） | gable・hip・shed・flatのmesh |
| 穴なしsimple直交polygon（concaveを含む） | 一体のflat屋根face |
| 対応するsimple直交footprint、ずれた帯形状、branch network | solve済みの一体gable mesh。hip面が残る場合があります |
| 凸の平行四辺形・台形・一般四辺形 | gable・shed・flat mesh。gable方向はseedで選択 |
| 対応する任意角度のsimple polygon（concaveを含む） | 全外周をeaveとするhip mesh |
| 対応する非直交compound footprint。隣接軒supportが平行・逆向きのterminal capを持つもの | 一体のgable/hip混合mesh。極大な互換gable端の候補集合をseedで選択 |

未解決のpolygon event、非terminal・partial・非平行supportのcompound gable端、複合shedは未対応です。
穴、接触・自己交差した境界、非平面入力、探索未完了も明示的に失敗します。
屋根表面には意図した外周境界があります。壁や厚みは別途作成します。

屋根接続は建物全体で構成してから、決定済みのGraphを固定してsolveします。
[段階別coverage](python/docs/END_TO_END_EVALUATION.md)でRoofGraph、solve、mesh、
実際のBlender変換を分けて報告します。grid stress corpusは全体coverageではありません。
未解決のpolygon event、対応するgable end modelの範囲、探索未完了が制約として残ります。
全faceのsupport planeとpitchが明示された問題は、topologyを固定して線形solveします。
planeが未指定の問題では汎用covariance optimizerを使います。
[embeddingの性能と検証](python/docs/PLANE_EMBEDDING.md)を参照してください。
[任意角度の対応範囲と実測](python/docs/ARBITRARY_ANGLE_ROOFS.md)ではhip・terminal gable・単一四辺形を別corpusで検証しています。
terminalモデルには、隣接する軒supportの平行・逆向き関係と三角capのincidenceが必要です。
平行な辺の組すべてをgableと解釈する方式ではありません。

## インストールと使い方

1. [`roof_generator-1.5.0.zip`](packages/roof_generator-1.5.0.zip) を **Download raw file** で保存します。
2. **Edit → Preferences → Add-ons → Install from Disk**でインストールし、**Roof Generator**を有効にします。
3. Object Modeで、面を張った平面footprint meshを選択します。
4. サイドバー（**N**）→ **Roof**で屋根種別、勾配、軒高offset、seedを設定し、**Generate roofs**を押します。

インストール済みのaddonを置き換える場合は、Preferencesで削除してからZIPを
インストールしてください。Blenderの上書きインストールでは不要なファイルが残る場合があります。

pipや外部wheelの導入は不要です。footprintごとに共有頂点・UV・マテリアルと
`roof_cell_i` / `roof_feature_i`のprovenance属性を持つ通常mesh objectを出力します。
回転・移動・非一様scaleはApplyせず扱えます。batchは全入力を検証してからsceneを変更します。
変換ボタンはUndoに対応します。屋根自体をGeometry Nodes内で計算する方式は未実装です。
土台のGeometry Nodes生成は、**N → Building → Create Base Meshes**から利用できます。
Width・Depth・Seed・Heightをmodifierで編集でき、RoofをONにすると現在の屋根生成APIへ接続します。
屋根が未対応でも土台と壁は残ります。

同じ入力・設定・seedなら同じ候補を選びます。Blenderではsource objectのlocal方向を
参照方向に使います。座標APIで同じ物理的選択を保つには、footprintと一緒に
`reference_direction`も回転してください。完全対称形の方向の曖昧さを、この明示的な
参照方向で扱います。

## 設計・開発

現在の構成は [ARCHITECTURE.md](ARCHITECTURE.md)、ツールとテストは
[python/README.md](python/README.md)、研究との対応は
[research mapping](python/docs/ROOF_PART_INTERPRETATION_RESEARCH.md)、実測は
[canonical measurements](python/docs/END_TO_END_EVALUATION.md)を参照してください。

```bash
python -m pip install -r python/requirements.txt  # 開発用oracleのみ
python -m unittest discover -s python/tests
python python/build_addon.py
blender -b --factory-startup --python-exit-code 1 --python python/blender_smoke_test.py -- --zip dist/roof_generator-1.5.0.zip
```

`addon/roof_generator/core/`が生成pipelineを所有します。Blender adapterは
`addon/roof_generator/`、inspection・実測・testは`python/`、配布ZIPは`packages/`、
研究資料への参照は[reference/](reference/README.md)にあります。

## ライセンス

source・tools・testsは**GPL-3.0-or-later**です。商用利用は可能ですが、配布にはGPLの
ライセンス・source提供等の条件があります。runtimeはBlenderとPython標準ライブラリを
使います。開発専用のNumPy、Shapely/GEOSにはそれぞれの権利条件があります。
[LICENSING.md](LICENSING.md)と[third-party notices](addon/roof_generator/THIRD_PARTY_NOTICES.md)を参照してください。

# Architectural authority: audit and end-constraint result

この報告の全corpus・性能の数値はproduction `449fe1d`の測定である。
その後の[one-line適用範囲の修正](ROOF_END_CONSTRAINTS.md)では、ずれた短辺接触を
端制約生成前に拒否した。更新後の全corpus再測定が終わるまで、以下の数値を
最新revisionの測定結果とは扱わない。

適用範囲修正後は139 tests（79.678s）が成功した。更新ZIPの19入力を
実operatorで検証し、前段階の成功11入力のcandidate IDはすべて同一だった。
offsetのtall入力は、後段のjunctionではなく端制約生成で拒否される。
[追加検証の記録](authority/offset-end-gate/verification.json)と
[operator結果](authority/offset-end-gate/operator.json)は前段階の測定と分けて保存した。

ArchitecturalPartを迂回してCell primitiveからrelationを再解釈する経路は、開始時のコードで実証した。現在はresolved architectureと全体の端制約をcompositionの入力にした。今回実装したのはgable要求のshared/T構成の制約と、狭いbranchのcorner-T extensionである。

**報告された工場屋根の因果除去は未確認。** 「全valleyにrelationという由来があるから問題は確認できなかった」という結論は撤回する。provenanceは生成経路の記録であり、屋根への採用根拠を証明しない。

## Authority audit

最初の[監査](ARCHITECTURAL_AUTHORITY_AUDIT.md)はproduction algorithmを変更する前にコミットした。

| Stage | 修正後のauthority | Output / decision |
| --- | --- | --- |
| Partition | Footprintとminimum certificate | Cells、geometry、provenance。屋根構成は決めない |
| Architecture | Member軸、関係の候補、全memberの端制約と対称性 | shared/T configurationとPart ownership |
| Topology candidate | 上記configuration | 実装可否を検証して固定incidenceの候補を生成 |
| Junction planning | selected end choicesとreceiver/branch | 対応済み接続のport applicabilityを検証 |
| GeometryProblem | 決定済みRoofGraph | 座標・高さ・勾配制約 |
| Solver | RoofGraphとGeometryProblem | 固定incidenceのembedding。構成は再選択しない |

## Data flow

Before:

```text
prepare_generation → minimum partitions → ArchitecturalPartGraph
→ score resolved axes → compose(Decomposition)
→ independent Cell RoofGraphs → rediscover contacts from ports
→ terminal/middle graft → RoofGraph → problem → solve
```

After:

```text
prepare_generation → minimum partitions → architectural member domains
→ resolve axes/analytic contacts → evaluate architectural score
→ intersect global end obligations + exact end symmetry
→ publish shared/T choices and corresponding Part ownership
→ compose(ResolvedArchitecture with RoofEnds)
→ member incidence templates → selected junction operation
→ RoofGraph + feature causes → problem → fixed-topology solve
```

L/U/many-branchで独立Cell RoofGraphの構築数は2/3/5から0になった。この最初の境界修正だけでは最終geometryは変わらなかった。Partを渡しただけで工場屋根を直したとは扱わない。

## End constraints and feature adoption

[実装範囲と研究対応](ROOF_END_CONSTRAINTS.md)を参照。HuのRはtriangular roof sideの許可であり、単純なopen/cap boolではない。形状制約とconnectionを分け、同じ端の競合・shared所有の競合・exact whole-member symmetryをcompositionより前に検証する。Hu全体のroof probability、half-hip、一般のmergeは実装していない。

cornerというanalytic relationにはshared/Tの候補を保持する。selected configurationがsharedなら両端をcompound junctionへ渡し、Tならbranchの内側端を延長で消費する。未対応Tをsharedへfallbackしない。

`test_roof_ends.py`は生成器から期待値を作らず、同一端のone-line/L競合、対称な選択、端configurationの正本、narrow corner-Tのliteral4面、solverへのGraph同一性を検証した。旧candidate集合は残し、その集合のseed契約を維持した。新しい構成を加えた全体集合では、同じseedの出力が変わり得る。

代表[10ケースのoperator比較](authority/end-state/gallery/index.html)は、Cells・Parts・resolved choices・最終Graphを並べる。各valleyのrelationだけでなく、そのrelationで選択されたshared/T状態をJSONと図で追える。画像を候補の採点には使わない。

独立に固定したnarrow corner-T例は、outline `(0,0),(12,0),(12,6),(4,6),(4,12),(0,12)`、seed2。beforeはshared（hip2/valley1）、afterはextension（hip0/valley2）。receiver ridgeを保ち、branch ridgeをreceiver slopeで終端する。この変更は「谷を減らした」証拠ではなく、以前作れなかった研究対応の構成を作れた証拠である。

## Factory-roof case

ユーザーの形は、重ならずにずれて辺で接する2長方形、1つのmesh object。四ブロックのSや3つの曲がったsegmentという以前のprobeは、この形の再現とは扱わない。

wide probeのoutlineは `(0,0),(12,0),(12,6),(16,6),(16,12),(4,12),(4,6),(0,6)`。下の12×6矩形と上の12×6矩形が長辺の一部で接する。1面と、共有辺をnode化した2面の両方を実operatorで検証した。tall/mixedも含む6入力はbefore/afterともunsupported、失敗時のsceneはatomic。wideはparallel、tallはcontinuation、mixedはpartial_endで止まる。

選択されたRoofGraphがないので、before/after Graphや「不要featureが消えた原因」は提示できない。[operator全件記録](authority/end-state/operator-after.json)と[診断partition](authority/end-state/inspection-end-state.json)を保存した。診断のfirst partitionをselected architectureと誤表示しない。factory regressionが修正済みという受け入れ条件は未達。

## Coverage

同一frozen corpus、seed0、同じ探索budget。表のBlenderは更新ZIPで実際に変換・validateした数。core不成功で未試行だった入力をBlender失敗とは数えない。

| Corpus | before RoofGraph | after RoofGraph | after solve | after mesh | after Blender |
| --- | ---: | ---: | ---: | ---: | ---: |
| orthogonal_grid_stress (1000) | 3 | 3 | 3 | 3 | 3 |
| nonuniform_orthogonal (150) | 0 | 0 | 0 | 0 | 0 |
| structured_orthogonal (103) | 13 | 13 | 13 | 13 | 13 |
| convex_quadrilateral (48) | 48 | 48 | 48 | 48 | 48 |
| structured_oblique (43) | 0 | 0 | 0 | 0 | 0 |
| general_simple_polygon_probe (40) | 0 | 0 | 0 | 0 | 0 |
| branch network (100) | 100 | 100 | 100 | 100 | 100 |

supported / unsupported / incompleteの全件集計は[outcomes](authority/end-state/outcomes.json)。candidate集合の集計は[coverage](authority/end-state/coverage-end-state.json)。branch100は[別corpus](authority/end-state/branch-end-state.json)。生のJSONLは再生成可能なignored出力に置き、manifestにhashを保存する。

## Remaining blockers

| Contact / decision | 現在の判定 | 未完事項 |
| --- | --- | --- |
| parallel | inter-part contactでも屋根junction化の根拠は不足 | arbitrary staggered長辺接続のGraph ruleを発明しない |
| continuation | gable end obligationは持てるがGraph mergeは未実装 | collinear equal-width mergeとoffset/width-stepを分ける |
| partial_end | roof configuration / incidenceの一般則が不足 | internal扱いかinter-part扱いかだけで採用を決めない |
| shared corner | globally compatibleなら既存terminal incidenceを使用 | relation labelだけで強制しない |
| narrow isolated corner-T | 実装済み、literal incidenceとsolveで検証 | 等幅・複数corner-Tはunsupported |
| symmetry | whole-member endsのexact reflectionを制約 | partial root matchesを推測で補完しない |

以前のboundary-stage分類A–Eの疑いを、そのまま確定原因へ昇格させない。Part内部であることは吸収・mergeの具体則ではなく、provenanceがあることは屋根採用の根拠ではない。代替partition/axesが通るケースと、資料・情報不足のケースを分けてdiagnosticsに残した。

## Ranking and solver boundary

architectural scoreとend configurationをoperation availabilityより先に記録する。constructible集合とそのうちのbest-score seedable集合は別。未知relationもavailabilityを理由に好ましいarchitectureへ置換しない。新end choices自体への独自の見た目scoreは追加しない。

solver/optimization production codeは開始SHAから変更していない。候補Graph、problem face loops、boundary ownership、embedding後のGraph同一性を確認した。solverが解けるように等幅corner-Tを別Graphへ変形する修正はしていない。

## Performance

同じ6-fixture benchmark、各3測定、2warmup、24-building batch。before/currentを重いcoverage処理の終了後に直列で実行した。unsupported例のcore_totalはsolveを含まないため、その値を完成meshの性能とは呼ばない。

| Case | before generation ms | after generation ms | before core_total ms | after core_total ms | mesh before / after |
| --- | ---: | ---: | ---: | ---: | --- |
| orthogonal_U | 13.02 | 21.21 | 373.21 | 362.26 | True / True |
| cross | 16.11 | 20.35 | 100.48 | 86.16 | True / True |
| residential_multi_reflex | 9.97 | 13.92 | 9.97 | 13.92 | False / False |
| grid_14 | 30.23 | 60.27 | 30.23 | 60.27 | False / False |
| grid_20 | 62.72 | 136.32 | 62.72 | 136.32 | False / False |
| grid_40 | 376.75 | 2740.09 | 376.75 | 2740.09 | False / False |

計測raw dataは[before](authority/end-state/mesh-performance-end-before-serial.json) / [after](authority/end-state/mesh-performance-end-after-serial.json)。候補評価・全体制約によるコスト増はそのまま報告する。永続cacheやspeedupのためのarchitecture変更は加えていない。端の組合せは有限だが組合せ的で、yield前の競合候補の探索budgetは今後の課題。

## Verification and commits

- 開始production SHA: `0210d7900c3a4340ddd5b22e05a673926332bbc7`
- 終了production SHA: `449fe1d8ea81bf75a45cda1b42a3723cfd3222d0`
- `f573932` Audit architectural authority in roof composition
- `9e0fbf1` Reproduce decomposition authority bypass at composition boundary
- `24a22a0` Make resolved architecture authoritative for roof composition and feature causes
- `c6cdc7f` Resolve compound membership before topology construction
- `449fe1d` Resolve global roof end choices before junction composition
- 138 tests passed、104.060s。ZIPとsourceのbyte一致を確認。
- Blender4.3.2 installed-ZIP smoke、UV/material、transform、atomic failureを検証。
- baselineのCI全5 job成功は開始時の情報。今回のCIは未実行、pushなし。
- 最終evidence/package commitと作業treeの状態は対話の最終報告に記す。既存untracked `.serena/` と `.roof-deps/` は保存した。

旧boundary-stage evidenceは`authority/manifest.json`、end-state後は[新manifest](authority/end-state/manifest.json)。rawのsource_shaが実行時の親checkout HEADを指すことがあるため、source stageとarchive hashを併記し、baseline snapshotのrevisionと混同しない。

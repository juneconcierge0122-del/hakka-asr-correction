# Technical Snapshot: Hakka TTS
_2026-03-17 · June · **v3**_

## Repo
https://github.com/juneconcierge0122-del/hakka-espeak (branch: `master`)

---

## 版本演進

| | v1 | v2 | **v3** |
|---|---|---|---|
| Voice | `en` | `hak` | **`en` (IPA mode)** |
| 音素 | raw IPA | espeak `ph_hakka` 原生 | **raw IPA per-syllable** |
| 聲調 | `[[t:s,e]]` pitch tag | espeak 六聲調映射 | **per-syllable pitch control** |
| Bug | — | 數字被念出 (`1`,`6`,`3`) | ✅ **Fixed** |

## 核心邏輯 (v3)

```
漢字 → formog2p(IPA) → SyllableInfo[] → per-syllable espeak_Synth(IPA, pitch) → concat PCM → WAV
```

### v2→v3 修了什麼
- **Bug**: espeak-ng IPA mode 不認 `[[t:start,end]]`，把裡面的數字當文字念出
- **Fix**: 拆成逐音節合成，每個 syllable 獨立呼叫 `espeak_Synth`，透過 `espeak_SetParameter(PITCH, value)` 控制聲調高低

### 關鍵結構
- `SyllableInfo(ipa, tone, pitch)` — formog2p token 解析後的結構
- `_TONE_PITCH` dict — 聲調 contour → (start, end) pitch，取平均作為該音節 pitch
- `_synth_one_syllable()` — 單音節 IPA→PCM
- `synthesize()` — 迴圈合成 + 串接

## v3 測試結果

| ID | 文字 | 腔調 | 音素 | 音長 |
|----|------|------|------|------|
| T1 | 天公落水 | hak_sx | `tʰien(24) kuŋ(24) lok(5) sui(31)` | 1.32s |
| T2 | 客家人愛唱歌 | hak_hl | `hak(5) ka(53) ŋin(55) oi(11) ʈ͡ʂʰoŋ(11) ko(53)` | 3.35s |
| T3 | 阿爸食飯無？ | hak_dp | `a(33) pa(33) ʂit(54) pʰon(53) mo(113)` | 1.88s |

3/3 passed.

## 現階段限制
- 逐音節合成的接合處不自然（無 co-articulation）
- espeak `en` voice 音色非客語母語者
- formog2p OOV：南四縣、饒平詞庫覆蓋率低
- pitch 只取 contour 平均，無聲調動態變化

## 待辦事項（下次銜接）
- [ ] 音節接合平滑化（crossfade / overlap-add）
- [ ] 聲調動態：用 pitch contour 而非單一值（分段線性插值）
- [ ] 聲學後端升級：VITS / FastSpeech2 + 客語語料
- [ ] 客語語音語料蒐集（formospeech / 客委會開放資料）
- [ ] OOV 處理：接教育部客語辭典補 formog2p 缺字
- [ ] 評估指標：MOS 主觀 / MCD 客觀
- [ ] 整合 ASR post-correction pipeline

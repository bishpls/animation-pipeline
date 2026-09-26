| Scope | Model | API turns | Input | Cache write | Cache read | Output |
|---|---|---:|---:|---:|---:|---:|
| all sessions | claude-fable-5-1 | 193 | 3,602 | 13,303,088 | 23,350,633 | 512,972 |
| all sessions | claude-opus-5-5 | 5,302 | 10,854 | 37,745,274 | 2,910,181,780 | 6,787,912 |
| all sessions | _all | 5,495 | 14,456 | 51,048,362 | 2,933,532,413 | 7,300,884 |
| Producer session / main | claude-opus-5-5 | 1,520 | 3,166 | 12,227,168 | 944,197,108 | 1,858,248 |
| Producer session / subagents | claude-fable-5-1 | 57 | 856 | 2,145,835 | 3,605,036 | 204,705 |
| Producer session / subagents | claude-opus-5-5 | 1,207 | 2,414 | 6,044,321 | 550,406,555 | 1,316,057 |
| Producer session / subagents | _all | 1,264 | 3,270 | 8,190,156 | 554,011,591 | 1,520,762 |
| Fable's paper world / main | claude-opus-5-5 | 1,679 | 3,474 | 12,147,474 | 986,767,029 | 2,176,807 |
| Fable's paper world / subagents | claude-fable-5-1 | 136 | 2,746 | 11,157,253 | 19,745,597 | 308,267 |
| Fable's paper world / subagents | claude-opus-5-5 | 896 | 1,800 | 7,326,311 | 428,811,088 | 1,436,800 |
| Fable's paper world / subagents | _all | 1,032 | 4,546 | 18,483,564 | 448,556,685 | 1,745,067 |

| Paid call | Calls | Detail |
|---|---:|---|
| elevenlabs:music.compose | 68 | seconds 2,425; model music_v2_5 ×68 |
| elevenlabs:sfx | 30 |  |
| elevenlabs:stems | 13 |  |
| elevenlabs:tts | 120 | chars 8,611; model eleven_v3 ×112; model eleven_multilingual_v2 ×8 |
| gemini:image | 8 | model gemini-3-pro-image ×8 |
| gemini:video-review | 4 | model gemini-3.1-pro-preview ×4 |
| higgsfield:bytedance/seedance-2.5/text-to-video | 13 | seconds 65 |
| openai:image | 280 | n 316, usage_input_tokens 493,027, usage_output_tokens 793,495, failed 3; model gpt-image-2.5-flare ×1; size 2160x3840 high ×31; model gpt-image-2.5-sunburst ×279; size 2160x3840 max ×1; size 1056x1056 high ×105; size 2880x2880 high ×2; size 1024x1024 high ×33; size 2160x2880 high ×1; size 3456x1944 high ×1; size 2880x2160 high ×3; size 3456x1936 high ×1; size 1392x1392 high ×6; size 3072x2304 high ×1; size 3840x2160 high ×2; size 3840x1280 high ×5; size 3840x1600 high ×2; size 2048x2560 high ×72; size 1696x1696 high ×1; size 768x768 high ×2; size 2560x1440 high ×5; size 1536x1536 high ×5; size 2048x2048 high ×1 |

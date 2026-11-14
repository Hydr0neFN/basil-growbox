# Home Assistant 整合

裝置透過 ESPHome 原生 API 對外開放（`Noise_NNpsk0_25519_ChaChaPoly_SHA256` 加密，金鑰放在 `secrets.yaml`），連到一台跑 Home Assistant 的樹莓派 4。它沒有本機網頁介面，也沒有 MQTT——HA 是刻意設計成唯一的介面（`basil.yaml` 裡有一段註解解釋為什麼移除了 `web_server:`：ESP8266 能同時服務的連線數非常有限，瀏覽器若開著網頁介面的 SSE 串流，會直接跟 HA 的 API 連線搶同一個有限的名額）。

| 類別 | 用途 |
|---|---|
| `sensor` | 土壤濕度 %、土壤電壓（診斷用）、水箱 %、水箱深度、水箱距離（診斷用）、箱內溫度、箱內濕度、WiFi 訊號、運作時間 |
| `binary_sensor` | 需要澆水、水箱見底、排水異常 |
| `switch` | 補光燈（補水泵浦刻意**不**對外開放——一個沒有計時保護的泵浦開關，被放進別人的自動化裡是個風險） |
| `number` | Dose（澆水量，cm）、Max cycles（最大循環數）、Stop at（停止門檻 %）、Water below（觸發門檻 %）、Lockout（鎖定時間，小時） |
| `button` | Water now（立即澆水）、Calibrate: start fill（校正：開始注水）、Calibrate: save dose（校正：儲存澆水量）、Clear drain fault（解除排水異常） |

三個告警自動化，狀態變化時會發通知：

- **排水異常**——鎖定當下立即通知，並附上解除異常按鈕的連結。
- **水箱見底**——延遲 5 分鐘，過濾掉淹灌過程中正常的短暫水位下降。
- **裝置離線**——`sensor.basil_uptime` 變成 `unavailable` 超過 30 分鐘才通知，這個長度足以撐過 HA 重啟或一般的 WiFi 短暫抖動，不會為了沒事而吵醒任何人。

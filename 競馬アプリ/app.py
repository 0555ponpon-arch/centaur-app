from flask import Flask, render_template, request, jsonify
import os

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/get_training_data', methods=['POST'])
def get_training_data():
    req_data = request.get_json()
    
    race_title = "セントウルステークス 追い切り診断"
    
    all_centaur_entries = [
        "カルプスペルシュ", "クラスペディア", "タマモイカロス", "タマモブラックタイ",
        "ダイヤモンドノット", "ティニア", "ビッグシーザー", "ピューロマジック",
        "ファストネットワーク", "フリッカージャブ", "プロトポロス", "ママコチャ",
        "ムイ", "メイショウヨゾラ", "ヤブサメ", "ヨシノイースター", "レッドモンレーヴ"
    ]
    
    verified_data = {
        "ダイヤモンドノット": {
            "w1_time": "栗坂 良 4F 51.9 - 37.8 - 25.2 - 13.2 (一杯に追う・単走)",
            "w1_eval": "やや反応が鈍く伸びも目立つ感じではない。少し不安残る追い切り。"
        },
        "タマモブラックタイ": {
            "w1_time": "栗坂 良 4F 54.4 - 39.3 - 25.3 - 12.2 (馬なり余力)",
            "w1_eval": "この時計なら余裕の走り。伸縮性あるフォームで背腰の連動性も良い。"
        },
        "ピューロマジック": {
            "w1_time": "栗坂 良 4F 53.3 - 38.8 - 25.6 - 12.8 (馬なり余力・単走)",
            "w1_eval": "折り合いは上手くついている。終いはやや渋い反応だが体自体は悪くなさそう。"
        },
        "フリッカージャブ": {
            "w1_time": "栗坂 良 4F 50.8 - 36.5 - 23.8 - 12.1 (一杯に追う)",
            "w1_eval": "メリハリの利いた追い切りで良い負荷。推進力も上々でほぼ仕上がった印象。"
        },
        "ママコチャ": {
            "w1_time": "栗ＣＷ 良 5F 66.7 - 51.2 - 36.8 - 11.2 (一杯に追う・単走)",
            "w1_eval": "動けているが追い出してからのフォームが少し伸び切った印象。フォームに課題。"
        },
        "メイショウヨゾラ": {
            "w1_time": "美Ｗ 良 5F 66.0 - 51.0 - 37.4 - 11.2 (G前仕掛け・単走)",
            "w1_eval": "キビキビとした動きで調子は良さそう。重心が前に行って伸びも目立つ好仕上がり。"
        },
        "ヨシノイースター": {
            "w1_time": "栗坂 良 4F 52.0 - 37.6 - 24.2 - 12.4 (叩き一杯・単走)",
            "w1_eval": "ここ数戦の中では少し反応が鈍く、ラチを頼る面も。前走より状態面はどうか。"
        },
        "レッドモンレーヴ": {
            "w1_time": "美Ｗ 良 6F 82.7 - 66.5 - 51.2 - 37.0 - 11.3 (馬なり余力)",
            "w1_eval": "折り合いも非常に良く心身のバランスが良い。休み明けだが動ける態勢。"
        }
    }
    
    horses_data = []
    
    for name in all_centaur_entries:
        if name in verified_data:
            horses_data.append({
                "name": name,
                "w1_time": verified_data[name]["w1_time"],
                "w1_eval": verified_data[name]["w1_eval"],
                "final_time": "最終追い切りデータ待ち",
                "final_eval": "水曜追切後に更新予定"
            })
        else:
            horses_data.append({
                "name": name,
                "w1_time": "計測データなし（枠外）",
                "w1_eval": "順調に調整中",
                "final_time": "-",
                "final_eval": "データ確認中"
            })
            
    return jsonify({
        "race_name": race_title,
        "horses": horses_data
    })

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
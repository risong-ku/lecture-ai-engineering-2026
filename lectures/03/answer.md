# 第3回 解答

## 演習

- 第1回（素のLLM）とエージェントの回答の違い： LLMが持つ知識から回答を捏造するのではなく、tool callで用語集を収集し、そこに含まれる用語についてのクイズを作れるようになった
- `--trace` で見えたツール呼び出し（ツール名と引数）： 1回（make_quiz）
- 1つの質問での LLM 呼び出し回数（`requests`）：2回
- 追加したツールと、docstring に書いた説明：以下のとおり

def make_quiz(lecture: int) -> str:
    """指定した回の用語から 1つを選び、
    確認問題と答えを返す。
    「第2回の確認問題を出して」のように、
    復習用の問題を求められたときに使う。
    """
    terms = [term for term in load_glossary() if term["lecture"] == lecture]
    if not terms:
        return f"第{lecture}回の用語が用語集にありません。"

    term = random.choice(terms)
    return json.dumps(
        {
            "question": f"「{term['term']}」の意味は？",
            "answer": term["definition"],
        },
        ensure_ascii=False,
    )


## 宿題

- 取り組んだレベル：実装
- やったこと： --interactive引数をつけて実行した場合に学習内容を記録する機能を追加
- 結果： 以下の通り、学習内容を入力すると、ユーザー確認をした上でlearning_logにタイムスタンプ付きでログが保存されることを確認

@risong-ku ➜ /workspaces/lecture-ai-engineering-2026 (lec03) $ uv run python -m app.agent --interactive --trace "今日の学習内容を学習記録に保存して"
[model] gemini-3.5-flash-lite
学習の記録を保存するために、本日の学習内容（学んだことや振り返りなど）を教えていただけますでしょうか？

内容を教えていただきましたら、内容を確認の上で `learning_log/` に保存いたします。

--- trace ---
[usage] RunUsage(cost=Decimal('0.0002716'), details={'text_prompt_tokens': 522}, input_text_tokens=522, input_tokens=522,output_tokens=46, requests=1)
質問を入力してください（終了: 空入力）: ハーネスエンジニアリング

実行を要求されたツール: save_learning_log
引数: {"content": "学習内容: ハーネスエンジニアリングについて学習した。"}
この操作を許可しますか？ [y/N]: y
本日の学習内容として「ハーネスエンジニアリング」についての記録を保存いたしました。

関連する回：第3回

--- trace ---
[tool call]   search_glossary({'query': 'ハーネスエンジニアリング'})
[tool return] search_glossary -> [{"term": "ハーネス", "lecture": 3, "definition": "LLMの周りを、ループ・ツール・画面（UI）などで包み、実際に作業できるようにするプログラム。Claude CodeやPiはハーネスの例。Piは組…
[tool call]   save_learning_log({'content': '学習内容: ハーネスエンジニアリングについて学習した。'})
[tool return] save_learning_log -> 学習記録を learning_log/20261110-012911-270062.md に保存しました。…
[usage] RunUsage(cost=Decimal('0.0003005'), details={'text_prompt_tokens': 785}, input_text_tokens=785, input_tokens=785,output_tokens=26, requests=1, tool_calls=1)
質問を入力してください（終了: 空入力）: 

- 気づき・疑問： 再現性を確実に担保したい処理は、tool callを外出しして定義することでAIエージェントの機能を拡張できる
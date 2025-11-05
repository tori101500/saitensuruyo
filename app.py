import io
import os
import logging
import hashlib
import base64
import streamlit as st

# 外部URLによるrequests呼び出しは行いません（requests等は使用しない）
try:
    import google.generativeai as genai
    from PIL import Image
    _GENAI_AVAILABLE = True
except Exception:
    # google.generativeai / Pillow が無ければローカル比較にフォールバック
    _GENAI_AVAILABLE = False

logging.basicConfig(level=logging.INFO)

# デフォルトモデル名は環境変数で上書き可能
GEMINI_MODEL_DEFAULT = os.environ.get("GEMINI_MODEL", "gemini-2.0")

PROMPT_TEMPLATE = """
あなたは採点者です。以下の2つの画像（提出画像、模範解答画像）を比較して、点数(0-100) と簡潔な採点コメント（日本語）を JSON で返してください。
JSON フィールド:
- score: 数値（0-100）
- comment: 簡潔なコメント（最大200文字）
- issues: 必要に応じた検出事項（配列）
出力は純粋に JSON のみを返してください。
"""

def _sha256(b: bytes):
    return hashlib.sha256(b).hexdigest() if b else None

def resize_image_bytes(image_bytes: bytes, max_dim: int = 1024) -> bytes:
    """Pillow を使って画像をリサイズ（渡された bytes を JPEG 化して返す）"""
    if not image_bytes:
        return image_bytes
    try:
        img = Image.open(io.BytesIO(image_bytes))
        if img.mode != "RGB":
            img = img.convert("RGB")
        w, h = img.size
        if max(w, h) > max_dim:
            if w >= h:
                new_w = max_dim
                new_h = int(h * (max_dim / w))
            else:
                new_h = max_dim
                new_w = int(w * (max_dim / h))
            img = img.resize((new_w, new_h), Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=90)
        return buf.getvalue()
    except Exception:
        logging.exception("resize_image_bytes failed")
        return image_bytes

def _local_mock_grade(image_bytes=None, image_filename=None, model_image_bytes=None, model_image_filename=None):
    """外部呼び出しをしないローカル簡易採点"""
    def info(b, fname):
        if not b:
            return None
        return {"filename": fname or "unknown", "size_bytes": len(b), "sha256": _sha256(b)}

    submission_info = info(image_bytes, image_filename)
    model_info = info(model_image_bytes, model_image_filename)

    byte_similarity = None
    if image_bytes and model_image_bytes:
        a = image_bytes
        b = model_image_bytes
        minlen = min(len(a), len(b))
        if minlen == 0:
            byte_similarity = 0.0
        else:
            matches = sum(1 for i in range(minlen) if a[i] == b[i])
            byte_similarity = round(matches / minlen * 100.0, 2)

    # 非常に簡易なスコアリング（参考用）
    score = None
    if byte_similarity is not None:
        score = int(byte_similarity) if byte_similarity is not None else 0
        # clamp 0-100
        score = max(0, min(100, score))
    else:
        score = 0 if submission_info and model_info else 50

    return {
        "mock": True,
        "grading_type": "local_mock",
        "submission": submission_info,
        "model": model_info,
        "byte_similarity_percent": byte_similarity,
        "score": score,
        "comment": "外部APIには接続していません。ローカルの簡易比較結果です。実運用では google.generativeai を導入してモデルで採点してください。"
    }

def _call_gemini_local_sdk(api_key: str, model_name: str, submission_bytes: bytes, model_bytes: bytes):
    """
    google.generativeai SDK を利用してローカルからモデル呼び出しを行うラッパー。
    SDK内部でネットワーク通信は行われますが、requestsで直接URLを叩く実装は使いません（ユーザ要求に合わせた実装）。
    """
    if not _GENAI_AVAILABLE:
        return {"error": "google.generativeai が利用できません（未インストール）"}
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(model_name) if model_name else genai.GenerativeModel(GEMINI_MODEL_DEFAULT)

        # 画像は PIL.Image にして渡す（SDKが画像を受け取れる場合）
        imgs = []
        if submission_bytes:
            imgs.append(Image.open(io.BytesIO(submission_bytes)))
        if model_bytes:
            imgs.append(Image.open(io.BytesIO(model_bytes)))

        prompt = PROMPT_TEMPLATE
        # SDK 呼び出し: prompt と画像群を渡して生成
        # 注意: 実行環境の SDK 実装に依存するため、例外処理で安全にフォールバックする
        resp = model.generate_content([prompt] + imgs)
        # SDK の戻りは実装依存。可能な限りテキストを取得する
        cand = getattr(resp, "_result", None)
        if cand and getattr(cand, "candidates", None):
            text = cand.candidates[0].content.parts[0].text.strip()
            # 返されるものが JSON 文字列ならパースを試みる
            try:
                import json
                parsed = json.loads(text)
                return parsed
            except Exception:
                # パースできない場合は自由テキストを結果として返す
                return {"raw_text": text}
        return {"error": "モデルから有効な応答が得られませんでした"}
    except Exception as e:
        logging.exception("gemini sdk call failed")
        return {"error": f"gemini sdk error: {e}"}

def grade_submission(api_key=None, submission_text=None, image_bytes=None, image_filename=None, model_image_bytes=None, model_image_filename=None, model_name=None, timeout=10):
    """
    外部URLをrequestsで叩かずに「SDK経由」または「ローカル比較」で採点する関数。
    - google.generativeai が利用可能なら SDK 経由でモデルに採点を依頼する（SDK内部での通信は許容）。
    - 利用できない場合はローカルの簡易採点を返す。
    """
    # 画像はリサイズしてから送る（サイズが大きすぎると失敗することがあるため）
    try:
        sub_bytes = resize_image_bytes(image_bytes) if image_bytes else None
        mod_bytes = resize_image_bytes(model_image_bytes) if model_image_bytes else None

        if _GENAI_AVAILABLE and api_key:
            return _call_gemini_local_sdk(api_key=api_key, model_name=(model_name or GEMINI_MODEL_DEFAULT), submission_bytes=sub_bytes, model_bytes=mod_bytes)
        else:
            # SDKが無い or APIキー未指定の時はローカル採点で返す
            return _local_mock_grade(image_bytes=sub_bytes, image_filename=image_filename, model_image_bytes=mod_bytes, model_image_filename=model_image_filename)
    except Exception as e:
        logging.exception("grade_submission failed")
        return {"error": str(e)}

def main():
    st.title("自動採点アプリ（URL直接呼び出しなし）")
    st.write("外部URLをrequestsで直接叩かずに、google.generativeai SDK を使うか、SDKが無い場合はローカル比較で採点します。")

    api_key = st.text_input("GEMINI API キー（SDK利用時にのみ必要）", type="password")
    model_name = st.text_input("モデル名（例: gemini-2.0-flash）", value=GEMINI_MODEL_DEFAULT)

    uploaded_image = st.file_uploader("提出画像をアップロード（png/jpg 等）", type=["png","jpg","jpeg","bmp","tiff","gif"])
    image_bytes = None
    image_filename = None
    if uploaded_image:
        image_bytes = uploaded_image.read()
        image_filename = uploaded_image.name
        st.image(image_bytes, caption=image_filename, use_column_width=True)

    uploaded_model = st.file_uploader("模範解答画像をアップロード（任意）", type=["png","jpg","jpeg","bmp","tiff","gif"], key="model_uploader")
    model_image_bytes = None
    model_image_filename = None
    if uploaded_model:
        model_image_bytes = uploaded_model.read()
        model_image_filename = uploaded_model.name
        st.image(model_image_bytes, caption="模範: " + model_image_filename, use_column_width=True)

    if st.button("採点を実行"):
        if not image_bytes:
            st.error("提出画像をアップロードしてください。")
            return

        with st.spinner("採点中..."):
            result = grade_submission(api_key=api_key or None, submission_text=None, image_bytes=image_bytes, image_filename=image_filename, model_image_bytes=model_image_bytes, model_image_filename=model_image_filename, model_name=(model_name or None))

        if isinstance(result, dict) and result.get("error"):
            st.error(f"エラー: {result['error']}")
            st.json(result)
        else:
            st.success("採点完了")
            st.json(result)

if __name__ == "__main__":
    main()
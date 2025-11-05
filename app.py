import streamlit as st
import requests
import logging
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import base64
import mimetypes

# Gemini APIのエンドポイント（実際のエンドポイントは提供元ドキュメントを確認）
GEMINI_API_URL = "https://api.gemini.com/v1/grade"

def _requests_session_with_retries(retries=3, backoff=0.3, status_forcelist=(500,502,503,504)):
    s = requests.Session()
    retry = Retry(total=retries, backoff_factor=backoff, status_forcelist=status_forcelist, allowed_methods=frozenset(["POST","GET"]))
    adapter = HTTPAdapter(max_retries=retry)
    s.mount("https://", adapter)
    s.mount("http://", adapter)
    return s

def grade_submission(api_key, submission_text=None, image_bytes=None, image_filename=None, timeout=10):
    """
    Gemini APIを利用して採点を行う関数
    - 画像が与えられた場合は multipart/form-data で送信
    - multipart が失敗した場合は base64 を JSON に入れて再試行
    - タイムアウト・リトライ・JSONパースの保護を追加
    """
    headers = {
        "Authorization": f"Bearer {api_key}"
    }
    session = _requests_session_with_retries()

    try:
        if image_bytes:
            content_type = mimetypes.guess_type(image_filename or "")[0] or "application/octet-stream"
            files = {"image": (image_filename or "upload", image_bytes, content_type)}
            # requests が Content-Type を自動設定するので headers から Content-Type は外す
            resp = session.post(GEMINI_API_URL, files=files, headers=headers, timeout=timeout)
        else:
            headers["Content-Type"] = "application/json"
            payload = {"submission": submission_text}
            resp = session.post(GEMINI_API_URL, json=payload, headers=headers, timeout=timeout)

        resp.raise_for_status()
        try:
            return resp.json()
        except ValueError:
            return {"error": "レスポンスがJSONではありません", "raw": resp.text}

    except requests.exceptions.RequestException as e:
        logging.exception("grade_submission failed")
        # 画像送信で失敗した場合は base64 JSON でフォールバックを試みる
        if image_bytes:
            try:
                b64 = base64.b64encode(image_bytes).decode("ascii")
                headers["Content-Type"] = "application/json"
                payload = {"image_base64": b64, "filename": image_filename}
                if submission_text:
                    payload["submission"] = submission_text
                resp = session.post(GEMINI_API_URL, json=payload, headers=headers, timeout=timeout)
                resp.raise_for_status()
                try:
                    return resp.json()
                except ValueError:
                    return {"error": "レスポンスがJSONではありません", "raw": resp.text}
            except Exception as e2:
                logging.exception("fallback base64 failed")
                return {"error": str(e2)}
        return {"error": str(e)}

def main():
    st.title("自動採点アプリ（画像対応）")
    st.write("画像をアップロードして採点します。")

    # APIキー取得: st.secrets から、無ければ入力欄で受け付ける
    api_key = st.secrets.get("GEMINI_API_KEY") if hasattr(st, "secrets") else None
    api_key_input = st.text_input("API キー（未設定時のみ入力）", type="password", value="" if api_key is None else "********")
    if not api_key and api_key_input:
        api_key = api_key_input

    # 画像アップロードを受け付ける（必須）
    uploaded_image = st.file_uploader("画像をアップロード（png, jpg, jpeg, bmp, gif, tiff）", type=["png","jpg","jpeg","bmp","gif","tiff"])
    image_bytes = None
    image_filename = None
    if uploaded_image:
        try:
            image_bytes = uploaded_image.read()
            image_filename = uploaded_image.name
            st.image(image_bytes, caption=image_filename, use_column_width=True)
        except Exception:
            st.error("アップロード画像の読み取りに失敗しました。")

    if st.button("採点を実行"):
        if not image_bytes:
            st.error("画像をアップロードしてください。")
            return
        if not api_key:
            st.error("API キーが必要です。`.streamlit/secrets.toml` に GEMINI_API_KEY を設定するか入力してください。")
            return

        with st.spinner("採点中..."):
            result = grade_submission(api_key, submission_text=None, image_bytes=image_bytes, image_filename=image_filename)

        if isinstance(result, dict) and "error" in result:
            st.error(f"エラーが発生しました: {result['error']}")
            if "raw" in result:
                st.text_area("レスポンス（生）", value=result["raw"], height=200)
        else:
            st.success("採点が完了しました！")
            st.json(result)

if __name__ == "__main__":
    main()
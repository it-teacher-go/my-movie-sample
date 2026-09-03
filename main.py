import requests
import pandas as pd
import streamlit as st

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo


# --------------------------------------------------
# 페이지 기본 설정
# --------------------------------------------------
st.set_page_config(
    page_title="어제의 박스오피스",
    page_icon="🎬",
    layout="wide",
)

st.title("🎬 어제의 박스오피스")
st.caption("영화진흥위원회(KOBIS) 일별 박스오피스 기준")


# --------------------------------------------------
# 한국 시간 기준으로 '어제' 날짜 계산
# 배포 서버가 해외에 있어도 Asia/Seoul 시간을 사용합니다.
# --------------------------------------------------
def get_yesterday_korea():
    korea_now = datetime.now(ZoneInfo("Asia/Seoul"))
    yesterday = korea_now - timedelta(days=1)

    # API가 요구하는 YYYYMMDD 형식
    return yesterday.strftime("%Y%m%d")


# --------------------------------------------------
# KOBIS API 호출 함수
#
# @st.cache_data를 사용하면 같은 날짜의 결과를
# 1시간 동안 기억하여 API를 다시 호출하지 않습니다.
# --------------------------------------------------
@st.cache_data(ttl=3600)
def get_daily_boxoffice(target_date):
    """
    KOBIS 일별 박스오피스 API에서 데이터를 가져옵니다.

    반환값:
        성공 시: (영화 목록, None)
        실패 시: (None, 오류 메시지)
    """

    # Streamlit Secrets에서 인증키를 안전하게 가져옵니다.
    try:
        api_key = st.secrets.get("KOBIS_KEY", None)
        if not api_key:
            st.error("🔑 KOBIS_KEY 값을 찾지 못했습니다.")
            st.write("현재 Secrets에 등록된 키 이름:", list(st.secrets.keys()))
            st.stop()

    except Exception as e:
        st.error(f"Secrets 읽기 오류: {e}")
        st.stop()

    # KOBIS 공식 API 주소
    url = (
        "https://www.kobis.or.kr/"
        "kobisopenapi/webservice/rest/boxoffice/"
        "searchDailyBoxOfficeList.json"
    )

    # API에 전달할 요청 변수
    params = {
        "key": api_key,
        "targetDt": target_date,
    }

    try:
        # 네트워크 요청
        response = requests.get(
            url,
            params=params,
            timeout=10,
        )

        # HTTP 상태코드 오류 확인
        response.raise_for_status()

        # JSON 형식으로 변환
        data = response.json()

    except requests.exceptions.Timeout:
        return None, (
            "⏰ **KOBIS 서버 응답 시간이 초과되었습니다.**\n\n"
            "잠시 후 다시 시도해 주세요."
        )

    except requests.exceptions.RequestException as error:
        return None, (
            "🌐 **KOBIS API 요청에 실패했습니다.**\n\n"
            f"네트워크 연결 또는 API 서버 상태를 확인해 주세요.\n\n"
            f"오류 내용: `{error}`"
        )

    except ValueError:
        return None, (
            "📄 **API 응답을 읽을 수 없습니다.**\n\n"
            "KOBIS API가 정상적인 JSON 데이터를 반환했는지 확인해 주세요."
        )

    # --------------------------------------------------
    # KOBIS는 인증키 오류 등이 발생해도
    # HTTP 상태코드 200을 반환할 수 있습니다.
    # 따라서 faultInfo를 반드시 확인합니다.
    # --------------------------------------------------
    if "faultInfo" in data:
        fault = data["faultInfo"]

        error_message = fault.get(
            "message",
            "알 수 없는 API 오류가 발생했습니다.",
        )

        return None, (
            "⚠️ **KOBIS API에서 오류를 반환했습니다.**\n\n"
            f"**오류 내용:** {error_message}\n\n"
            "다음을 확인해 주세요.\n"
            "- Streamlit Secrets의 `KOBIS_KEY`가 올바른지\n"
            "- 인증키가 정상적으로 발급되었는지\n"
            "- KOBIS Open API 서버가 정상인지"
        )

    # boxOfficeResult 확인
    boxoffice_result = data.get("boxOfficeResult")

    if not boxoffice_result:
        return None, (
            "📦 **박스오피스 결과를 찾을 수 없습니다.**\n\n"
            "API 응답 구조가 정상적인지 확인해 주세요."
        )

    # 영화 목록 가져오기
    movie_list = boxoffice_result.get("dailyBoxOfficeList", [])

    # 영화 목록이 비어 있는 경우
    if not movie_list:
        return None, (
            f"🎬 **{target_date}의 박스오피스 영화 목록이 없습니다.**\n\n"
            "다음을 확인해 주세요.\n"
            "- 해당 날짜의 박스오피스 집계가 완료되었는지\n"
            "- 조회 날짜가 올바른지\n"
            "- KOBIS API가 정상적으로 데이터를 제공하고 있는지"
        )

    return movie_list, None


# --------------------------------------------------
# 숫자로 된 문자열을 안전하게 숫자로 변환하는 함수
#
# KOBIS API는 숫자도 문자열로 보내기 때문에
# 정렬과 그래프를 위해 숫자로 변환해야 합니다.
# --------------------------------------------------
def to_number(value):
    try:
        return int(value)
    except (ValueError, TypeError):
        return 0


# --------------------------------------------------
# 어제 날짜 계산
# --------------------------------------------------
target_date = get_yesterday_korea()


# --------------------------------------------------
# API 데이터 가져오기
# --------------------------------------------------
with st.spinner("어제의 박스오피스를 불러오는 중입니다..."):
    movie_list, error_message = get_daily_boxoffice(target_date)


# --------------------------------------------------
# 오류가 발생했을 때 안내
# --------------------------------------------------
if error_message:
    st.error(error_message)
    st.stop()


# --------------------------------------------------
# 받아온 데이터를 DataFrame으로 변환
# --------------------------------------------------
rows = []

for movie in movie_list:
    rows.append(
        {
            # 숫자 문자열은 숫자로 변환
            "순위": to_number(movie.get("rank")),
            "영화명": movie.get("movieNm", ""),
            "개봉일": movie.get("openDt", ""),
            "관객수": to_number(movie.get("audiCnt")),
            "누적관객": to_number(movie.get("audiAcc")),
            "스크린수": to_number(movie.get("scrnCnt")),
        }
    )


df = pd.DataFrame(rows)


# --------------------------------------------------
# 순위 기준으로 정렬
# --------------------------------------------------
df = df.sort_values("순위").reset_index(drop=True)


# --------------------------------------------------
# 날짜 표시
# --------------------------------------------------
display_date = datetime.strptime(
    target_date,
    "%Y%m%d",
).strftime("%Y년 %m월 %d일")

st.subheader(f"📅 {display_date} 기준")


# --------------------------------------------------
# 1위 영화 표시
# --------------------------------------------------
top_movie = df.iloc[0]

st.markdown("## 🥇 오늘의 1위")

st.subheader(top_movie["영화명"])

# 지표 카드 3개
col1, col2, col3 = st.columns(3)

col1.metric(
    "당일 관객수",
    f"{top_movie['관객수']:,}명",
)

col2.metric(
    "누적 관객수",
    f"{top_movie['누적관객']:,}명",
)

col3.metric(
    "스크린수",
    f"{top_movie['스크린수']:,}개",
)


# --------------------------------------------------
# 관객수 상위 5편 막대그래프
# --------------------------------------------------
st.markdown("## 📊 관객수 상위 5편")

# 관객수 기준 내림차순으로 상위 5개 선택
top5 = (
    df.sort_values("관객수", ascending=False)
    .head(5)
    .set_index("영화명")
)

# Streamlit 기본 막대그래프
st.bar_chart(
    top5["관객수"],
)


# --------------------------------------------------
# 전체 박스오피스 표
# --------------------------------------------------
st.markdown("## 🎥 전체 박스오피스")

# 화면에 보여 줄 열만 선택
display_df = df[
    [
        "순위",
        "영화명",
        "개봉일",
        "관객수",
        "누적관객",
        "스크린수",
    ]
].copy()

# 숫자를 보기 좋게 콤마 형식으로 표시
for column in ["관객수", "누적관객", "스크린수"]:
    display_df[column] = display_df[column].map(
        lambda value: f"{value:,}"
    )

# 표 출력
st.dataframe(
    display_df,
    use_container_width=True,
    hide_index=True,
)


# --------------------------------------------------
# 하단 안내
# --------------------------------------------------
st.caption(
    "※ 데이터 출처: 영화진흥위원회(KOBIS) 오픈 API | "
    "같은 날짜의 데이터는 최대 1시간 동안 캐시됩니다."
)

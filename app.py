"""회원제 관심 종목 대시보드.

- SQLite3 회원 저장, bcrypt 비밀번호 해싱
- Gmail 앱 비밀번호로 인증 메일(인증 URL) 발송 -> 인증 완료 시 가입 확정
- 로그인 회원은 본인이 등록한 관심 종목만 조회 / 그래프 확인
"""
from datetime import date, datetime, timedelta

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import auth
import db
import stocks
from config import APP_BASE_URL, DEV_SHOW_LINK, mail_configured
from mailer import build_verify_url, send_verification_mail

st.set_page_config(page_title="관심종목 대시보드", page_icon="📈", layout="wide")
db.init_db()


# ---------------------------------------------------------------- 공통 유틸


def fmt_num(value) -> str:
    if value is None or pd.isna(value):
        return "-"
    return f"{value:,.0f}" if abs(value) >= 1000 else f"{value:,.2f}"


def current_user() -> dict | None:
    return st.session_state.get("user")


def label_of(row) -> str:
    """표시 이름이 심볼과 같으면 중복 표기를 피한다."""
    name, symbol = row["name"], row["symbol"]
    return symbol if name == symbol else f"{name} ({symbol})"


def deliver_token(email: str, token: str) -> None:
    """인증 메일 발송. 발송 불가한 개발 환경에서는 링크를 화면에 표시한다."""
    ok, message = send_verification_mail(email, token)
    if ok:
        st.success(message)
        return

    st.warning(message)
    if DEV_SHOW_LINK:
        st.info("개발 모드: 아래 링크를 열면 직접 인증할 수 있습니다.")
        st.code(build_verify_url(token), language="text")
    else:
        st.error("관리자에게 메일 설정을 문의해 주세요.")


# ------------------------------------------------------- 이메일 인증 처리


def handle_verification() -> None:
    token = st.query_params.get("verify")
    if not token:
        return

    ok, message = db.consume_token(token)
    st.query_params.clear()
    (st.success if ok else st.error)(message)


# ------------------------------------------------------------ 인증 화면


def render_login_tab() -> None:
    with st.form("login_form"):
        email = st.text_input("이메일", key="login_email")
        password = st.text_input("비밀번호", type="password", key="login_pw")
        submitted = st.form_submit_button("로그인", use_container_width=True)

    if submitted:
        try:
            st.session_state["user"] = auth.login(email, password)
            st.rerun()
        except ValueError as exc:
            st.error(str(exc))


def render_signup_tab() -> None:
    with st.form("signup_form"):
        email = st.text_input("이메일", key="signup_email")
        password = st.text_input(
            "비밀번호",
            type="password",
            key="signup_pw",
            help=f"{auth.MIN_PASSWORD_LEN}자 이상",
        )
        password2 = st.text_input("비밀번호 확인", type="password", key="signup_pw2")
        submitted = st.form_submit_button("인증 메일 받기", use_container_width=True)

    if not submitted:
        return

    error = auth.validate_signup(email, password, password2)
    if error:
        st.error(error)
        return

    try:
        _, token = auth.register(email, password)
    except ValueError as exc:
        st.error(str(exc))
        return

    deliver_token(email.strip(), token)
    st.caption("메일의 인증 링크를 열면 가입이 완료되고, 그 뒤에 로그인할 수 있습니다.")


def render_resend_tab() -> None:
    st.caption("인증 메일을 받지 못했거나 링크가 만료된 경우 다시 받을 수 있습니다.")
    with st.form("resend_form"):
        email = st.text_input("가입한 이메일", key="resend_email")
        submitted = st.form_submit_button("인증 메일 다시 보내기", use_container_width=True)

    if not submitted:
        return

    user = db.get_user_by_email(email)
    if user is None:
        st.error("가입 이력이 없는 이메일입니다. 먼저 회원가입을 진행해 주세요.")
    elif user["is_verified"]:
        st.info("이미 인증이 완료된 계정입니다. 로그인해 주세요.")
    else:
        deliver_token(user["email"], auth.issue_token(int(user["id"])))


def render_auth_page() -> None:
    # 로그인 폼은 화면 가운데 좁은 단에 배치한다.
    _, center, _ = st.columns([1, 2, 1])
    with center:
        st.markdown(
            "<h1 style='text-align:center;margin-bottom:0'>📈 관심종목 대시보드</h1>"
            "<p style='text-align:center;color:#6b7280;margin-top:6px'>"
            "회원가입 → 이메일 인증 → 로그인 후 내 관심 종목만 차트로 확인합니다.</p>",
            unsafe_allow_html=True,
        )

        if not mail_configured():
            st.warning(
                "메일 발송 설정이 없습니다. `.env` 에 GMAIL_USER / GMAIL_APP_PASSWORD 를 "
                "지정하면 실제 인증 메일이 발송됩니다."
            )

        tab_login, tab_signup, tab_resend = st.tabs(
            ["로그인", "회원가입", "인증 메일 재발송"]
        )
        with tab_login:
            render_login_tab()
        with tab_signup:
            render_signup_tab()
        with tab_resend:
            render_resend_tab()


# ------------------------------------------------------ 관심 종목 사이드바


def render_sidebar(user: dict) -> None:
    st.sidebar.markdown(f"**{user['email']}** 님")
    if st.sidebar.button("로그아웃", use_container_width=True):
        st.session_state.pop("user", None)
        st.rerun()

    st.sidebar.divider()
    st.sidebar.subheader("관심 종목 추가")

    with st.sidebar.form("search_form"):
        market = st.radio("시장", list(stocks.MARKETS), horizontal=True)
        keyword = st.text_input(
            "종목명 / 심볼 검색", placeholder="삼성전자, Tesla, AAPL ..."
        )
        searched = st.form_submit_button("검색", use_container_width=True)

    if searched and keyword.strip():
        spinner = "해외 종목 목록을 불러오는 중… (최초 1회는 시간이 걸립니다)"
        with st.spinner(spinner if market == "해외" else "검색 중…"):
            st.session_state["search_result"] = stocks.search_listing(keyword, market)

    result = st.session_state.get("search_result")
    if result is not None and not result.empty:
        for _, row in result.iterrows():
            label = f"{row['Name']} ({row['Code']})"
            if st.sidebar.button(
                f"➕ {label}",
                key=f"add_{row['Code']}",
                help=f"{row['Market']} 상장",
                use_container_width=True,
            ):
                ok, msg = db.add_watch(user["id"], row["Code"], row["Name"])
                (st.sidebar.success if ok else st.sidebar.warning)(msg)
                st.session_state.pop("search_result", None)
                st.rerun()
    elif result is not None:
        st.sidebar.caption("검색 결과가 없습니다. 아래에서 직접 입력해 주세요.")

    with st.sidebar.form("manual_form", clear_on_submit=True):
        symbol = st.text_input("심볼 직접 입력", placeholder="005930, TSLA, AAPL ...")
        display_name = st.text_input("표시 이름 (선택)")
        added = st.form_submit_button("추가", use_container_width=True)

    if added:
        symbol = symbol.strip()
        if not symbol:
            st.sidebar.error("심볼을 입력해 주세요.")
        else:
            with st.spinner("종목을 확인하는 중..."):
                valid = stocks.symbol_exists(symbol)
            if not valid:
                st.sidebar.error(f"{symbol} 시세를 찾을 수 없습니다. 심볼을 확인해 주세요.")
            else:
                name = display_name.strip() or stocks.resolve_name(symbol)
                ok, msg = db.add_watch(user["id"], symbol, name)
                (st.sidebar.success if ok else st.sidebar.warning)(msg)
                st.rerun()

    st.sidebar.divider()
    st.sidebar.subheader("내 관심 종목")
    rows = db.list_watchlist(user["id"])
    if not rows:
        st.sidebar.caption("등록된 종목이 없습니다.")
    for row in rows:
        col_name, col_del = st.sidebar.columns([3, 1])
        col_name.write(label_of(row))
        if col_del.button("🗑", key=f"del_{row['symbol']}", help="삭제"):
            db.remove_watch(user["id"], row["symbol"])
            st.rerun()


# ------------------------------------------------------------- 차트 화면


def render_single_chart(
    symbol: str, name: str, start: date, end: date, options: dict
) -> None:
    with st.spinner("시세를 불러오는 중..."):
        df = stocks.get_price(symbol, start, end)

    if df.empty:
        st.error(f"{name} ({symbol}) 데이터를 가져오지 못했습니다. 기간이나 심볼을 확인해 주세요.")
        return

    df = stocks.add_moving_averages(df)

    # 종목명과 핵심 지표를 차트 위에 둔다. (차트 안 제목은 범례와 겹쳐서 뺐다)
    last = df["Close"].iloc[-1]
    prev = df["Close"].iloc[-2] if len(df) > 1 else last
    change = last - prev
    pct = (change / prev * 100) if prev else 0.0

    st.markdown(f"#### {name} `{symbol}`")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("현재가", fmt_num(last), f"{change:+,.2f} ({pct:+.2f}%)")
    c2.metric("기간 내 고가", fmt_num(df["High"].max()))
    c3.metric("기간 내 저가", fmt_num(df["Low"].min()))
    c4.metric("최근 거래량", fmt_num(df["Volume"].iloc[-1]) if "Volume" in df else "-")

    fig = go.Figure()
    fig.add_trace(
        go.Candlestick(
            x=df.index,
            open=df["Open"],
            high=df["High"],
            low=df["Low"],
            close=df["Close"],
            name=name,
        )
    )
    for window, color, enabled in (
        (5, "orange", options["ma5"]),
        (20, "royalblue", options["ma20"]),
        (60, "purple", options["ma60"]),
    ):
        if enabled:
            fig.add_trace(
                go.Scatter(
                    x=df.index,
                    y=df[f"MA{window}"],
                    name=f"MA{window}",
                    line=dict(color=color, width=1),
                )
            )
    fig.update_layout(
        height=520,
        margin=dict(l=10, r=10, t=30, b=10),
        xaxis_rangeslider_visible=False,
        legend=dict(orientation="h", y=1.02, yanchor="bottom", x=1, xanchor="right"),
    )
    st.plotly_chart(fig, use_container_width=True)

    if options["volume"] and "Volume" in df:
        st.subheader("거래량")
        st.bar_chart(df["Volume"], height=200)

    if options["table"]:
        st.subheader("원본 데이터")
        st.dataframe(df.sort_index(ascending=False), use_container_width=True)


def render_compare_chart(rows, start: date, end: date) -> None:
    st.caption("기간 첫 거래일을 100 으로 맞춘 상대 수익률 비교입니다.")
    fig = go.Figure()
    summary = []

    for row in rows:
        df = stocks.get_price(row["symbol"], start, end)
        if df.empty:
            continue
        indexed = stocks.normalize(df["Close"])
        if indexed.empty:
            continue
        fig.add_trace(
            go.Scatter(x=indexed.index, y=indexed, name=row["name"], mode="lines")
        )
        summary.append(
            {
                "종목": row["name"],
                "심볼": row["symbol"],
                "종가": fmt_num(df["Close"].iloc[-1]),
                "기간 수익률(%)": round(float(indexed.iloc[-1]) - 100, 2),
            }
        )

    if not summary:
        st.error("비교할 데이터를 가져오지 못했습니다.")
        return

    fig.update_layout(
        height=520,
        margin=dict(l=10, r=10, t=30, b=10),
        yaxis_title="지수 (첫날 = 100)",
        legend=dict(orientation="h", y=1.02, yanchor="bottom"),
    )
    st.plotly_chart(fig, use_container_width=True)
    st.dataframe(
        pd.DataFrame(summary).sort_values("기간 수익률(%)", ascending=False),
        use_container_width=True,
        hide_index=True,
    )


def render_dashboard(user: dict) -> None:
    render_sidebar(user)

    st.title("📈 내 관심 종목")
    rows = db.list_watchlist(user["id"])

    if not rows:
        st.info("왼쪽 사이드바에서 관심 종목을 추가하면 차트가 표시됩니다.")
        return

    labels = {label_of(row): row for row in rows}

    top1, top2, top3 = st.columns([2, 1, 1])
    selected_label = top1.selectbox("종목 선택", list(labels.keys()))
    start = top2.date_input("시작일", datetime.now() - timedelta(days=365))
    end = top3.date_input("종료일", datetime.now())

    opt1, opt2, opt3, opt4, opt5 = st.columns(5)
    options = {
        "ma5": opt1.checkbox("MA5", value=True),
        "ma20": opt2.checkbox("MA20", value=True),
        "ma60": opt3.checkbox("MA60", value=False),
        "volume": opt4.checkbox("거래량", value=True),
        "table": opt5.checkbox("데이터 표", value=False),
    }

    if start >= end:
        st.error("시작일은 종료일보다 앞서야 합니다.")
        return

    tab_single, tab_compare = st.tabs(["개별 차트", "전체 비교"])
    with tab_single:
        target = labels[selected_label]
        render_single_chart(target["symbol"], target["name"], start, end, options)
    with tab_compare:
        render_compare_chart(rows, start, end)


# ------------------------------------------------------------------ main


def main() -> None:
    handle_verification()
    user = current_user()
    if user is None:
        render_auth_page()
    else:
        render_dashboard(user)


main()

"""FinanceDataReader 기반 시세 조회 (Streamlit 캐시 적용)."""
from datetime import date

import FinanceDataReader as fdr
import pandas as pd
import streamlit as st


@st.cache_data(ttl=60 * 30, show_spinner=False)
def get_price(symbol: str, start: date, end: date) -> pd.DataFrame:
    """일별 시세. 조회 실패 시 빈 DataFrame."""
    try:
        df = fdr.DataReader(symbol, start, end)
    except Exception:
        return pd.DataFrame()
    return df if isinstance(df, pd.DataFrame) else pd.DataFrame()


EMPTY_LISTING = pd.DataFrame(columns=["Code", "Name", "Market"])

# 같은 시장이라도 FDR 버전에 따라 동작하는 소스가 달라 순서대로 시도한다.
# (0.9.101 기준 "KRX" 는 응답이 깨져 있어 "KRX-DESC" 로 폴백된다.)
MARKETS: dict[str, tuple[str, ...]] = {
    "국내": ("KRX", "KRX-DESC", "KOSPI"),
    "해외": ("NASDAQ", "NYSE", "AMEX"),
}


def _normalize_listing(df: pd.DataFrame, market: str) -> pd.DataFrame:
    """소스마다 다른 컬럼명을 Code / Name / Market 으로 통일한다."""
    if df is None or df.empty:
        return EMPTY_LISTING

    code_col = next((c for c in ("Code", "Symbol") if c in df.columns), None)
    name_col = next((c for c in ("Name", "Korean Name") if c in df.columns), None)
    if code_col is None or name_col is None:
        return EMPTY_LISTING

    out = df[[code_col, name_col]].rename(columns={code_col: "Code", name_col: "Name"})
    out = out.dropna().astype(str)
    out["Market"] = market
    return out


@st.cache_data(ttl=60 * 60 * 12, show_spinner=False)
def get_listing(market: str) -> pd.DataFrame:
    """시장별 상장 종목 목록. 국내는 첫 성공 소스만, 해외는 거래소를 합쳐서 돌려준다."""
    sources = MARKETS.get(market, ())
    frames: list[pd.DataFrame] = []

    for source in sources:
        try:
            df = _normalize_listing(fdr.StockListing(source), source)
        except Exception:
            continue
        if df.empty:
            continue
        if market == "국내":
            # 국내는 한 소스에 전 종목이 들어 있으므로 먼저 성공한 것을 쓴다.
            # (소스명은 내부용이라 화면에는 거래소 이름으로 표시한다.)
            return df.assign(Market="KRX").drop_duplicates(subset="Code")
        frames.append(df)

    if not frames:
        return EMPTY_LISTING
    return pd.concat(frames, ignore_index=True).drop_duplicates(subset="Code")


def search_listing(keyword: str, market: str, limit: int = 20) -> pd.DataFrame:
    """종목명 또는 심볼로 검색한다."""
    listing = get_listing(market)
    kw = keyword.strip()
    if listing.empty or not kw:
        return EMPTY_LISTING

    hit = listing[
        listing["Name"].str.contains(kw, case=False, na=False)
        | listing["Code"].str.contains(kw, case=False, na=False)
    ]
    # 심볼/종목명이 정확히 일치하는 항목을 위로 올린다.
    exact = hit["Code"].str.upper().eq(kw.upper()) | hit["Name"].str.lower().eq(kw.lower())
    return hit.assign(_exact=~exact).sort_values("_exact").drop(columns="_exact").head(limit)


def resolve_name(symbol: str) -> str:
    """상장 목록에서 종목명을 찾는다. 못 찾으면 심볼을 그대로 돌려준다."""
    symbol = symbol.strip()
    # 6자리 숫자면 국내 코드이므로 해외 목록은 받아오지 않는다.
    order = ("국내", "해외") if symbol.isdigit() else ("해외", "국내")

    for market in order:
        listing = get_listing(market)
        if listing.empty:
            continue
        hit = listing[listing["Code"].str.upper() == symbol.upper()]
        if not hit.empty:
            return str(hit.iloc[0]["Name"])
    return symbol.upper()


def symbol_exists(symbol: str) -> bool:
    """최근 시세를 실제로 받아와 심볼 유효성을 확인한다."""
    today = date.today()
    df = get_price(symbol, date(today.year - 1, today.month, today.day), today)
    return not df.empty


def add_moving_averages(df: pd.DataFrame, windows=(5, 20, 60)) -> pd.DataFrame:
    df = df.copy()
    for w in windows:
        df[f"MA{w}"] = df["Close"].rolling(window=w).mean()
    return df


def normalize(series: pd.Series) -> pd.Series:
    """첫 거래일을 100 으로 맞춘 상대 수익률 지수."""
    clean = series.dropna()
    if clean.empty or clean.iloc[0] == 0:
        return clean
    return clean / clean.iloc[0] * 100

from __future__ import annotations
from typing import Dict, Any

from .http import HttpClient
from .secid import secid_of

# 东财单只证券信息接口（抓包/AKShare 使用的同一路径）
# fields 很长，默认直接返回 data 原始字段；你可以在外部自己挑字段做映射。
DEFAULT_FIELDS = (
    "f120,f121,f122,f174,f175,f59,f163,f43,f57,f58,f169,f170,f46,f44,f51,f168,f47,"
    "f164,f116,f60,f45,f52,f50,f48,f167,f117,f71,f161,f49,f530,f135,f136,f137,f138,"
    "f139,f141,f142,f144,f145,f147,f148,f140,f143,f146,f149,f55,f62,f162,f92,f173,f104,"
    "f105,f84,f85,f183,f184,f185,f186,f187,f188,f189,f190,f191,f192,f107,f111,f86,f177,f78,"
    "f110,f262,f263,f264,f267,f268,f255,f256,f257,f258,f127,f199,f128,f198,f259,f260,f261,"
    "f171,f277,f278,f279,f288,f152,f250,f251,f252,f253,f254,f269,f270,f271,f272,f273,f274,"
    "f275,f276,f265,f266,f289,f290,f286,f285,f292,f293,f294,f295"
)

def fetch_stock_quote(http: HttpClient, symbol: str, fields: str = DEFAULT_FIELDS) -> Dict[str, Any]:
    path = "/api/qt/stock/get"
    params = {
        "ut": "fa5fd1943c7b386f172d6893dbfba10b",
        "fltt": "2",
        "invt": "2",
        "fields": fields,
        "secid": secid_of(symbol, http),
        "_": "0",
    }
    j = http.get_json(path, params)
    return (j or {}).get("data") or {}
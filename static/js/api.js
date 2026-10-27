// static/js/api.js
// Flask 백엔드와의 모든 통신을 이 파일에서 관리한다.

// 상대경로를 쓴다. 'http://localhost:5000'을 하드코딩하면 같은 와이파이의 다른 기기나
// 배포 환경에서 접속했을 때 각 기기가 자기 자신을 찾아가 전부 실패한다.
const API_BASE_URL = '/api';

// =========================================
// 공통 요청 헬퍼
// 실패 시 백엔드가 보낸 {"success": false, "error": "..."} 의 error 메시지를 살린다.
// (본문을 읽지 않고 throw하면 사용자는 "HTTP 500"만 보게 된다)
// =========================================
async function request(path, options = {}, label = '요청') {
  try {
    const res = await fetch(`${API_BASE_URL}${path}`, options);

    let body = null;
    try {
      body = await res.json();
    } catch {
      body = null;
    }

    if (!res.ok) {
      throw new Error(body?.error || `HTTP ${res.status}`);
    }
    if (!body) {
      throw new Error('서버 응답을 읽지 못했습니다');
    }
    return body;
  } catch (err) {
    console.error(`${label} 실패:`, err);
    return { success: false, error: err.message };
  }
}

function jsonPost(body) {
  return {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  };
}

// =========================================
// POST /api/parse — SMS 파싱 (미리보기만, 저장하지 않음)
// =========================================
async function parseSMS(smsText) {
  return request('/parse', jsonPost({ sms: smsText }), 'SMS 파싱');
}

// =========================================
// POST /api/transactions — 거래 저장
// =========================================
async function saveTransaction(data) {
  return request('/transactions', jsonPost(data), '거래 저장');
}

// =========================================
// DELETE /api/transactions/<id> — 거래 삭제
// =========================================
async function deleteTransaction(id) {
  return request(`/transactions/${encodeURIComponent(id)}`, { method: 'DELETE' }, '거래 삭제');
}

// =========================================
// GET /api/transactions — 거래 내역 조회 (월 / 카테고리 / 상점명 검색)
// =========================================
async function getTransactions({ month, category, search } = {}) {
  const params = new URLSearchParams();
  if (month)    params.set('month', month);
  if (category) params.set('category', category);
  if (search)   params.set('search', search);

  return request(`/transactions?${params}`, {}, '거래 내역 조회');
}

// =========================================
// GET /api/stats — 대시보드 통계
// =========================================
async function getDashboardStats(month) {
  const params = new URLSearchParams();
  if (month) params.set('month', month);

  return request(`/stats?${params}`, {}, '통계 조회');
}

// =========================================
// GET /api/analysis — AI 분석 및 또래 비교
// 연령대 값이 한글이므로 URLSearchParams로 인코딩해서 보낸다.
// =========================================
async function getAIAnalysis(ageGroup, incomeGroup, month) {
  const params = new URLSearchParams();
  if (ageGroup)    params.set('age_group', ageGroup);
  if (incomeGroup) params.set('income_group', incomeGroup);
  if (month)       params.set('month', month);

  return request(`/analysis?${params}`, {}, 'AI 분석 조회');
}

export {
  parseSMS,
  saveTransaction,
  deleteTransaction,
  getTransactions,
  getDashboardStats,
  getAIAnalysis,
};

import Link from "next/link";

const sections = [
  "퍼널 구간별 원인 추적",
  "이상 탐지 규칙 설정",
  "가설 실험 결과 비교",
  "리포트 공유 및 협업",
];

export default function DocsPage() {
  return (
    <main className="min-h-screen bg-slate-950 px-6 py-12 text-slate-100 sm:px-10">
      <div className="mx-auto max-w-3xl rounded-2xl border border-slate-800 bg-slate-900/70 p-8">
        <p className="text-xs font-semibold tracking-[0.2em] text-emerald-300">FEATURE OVERVIEW</p>
        <h1 className="mt-3 text-3xl font-black">분석 기능 문서</h1>
        <p className="mt-4 text-sm leading-7 text-slate-300 sm:text-base">
          아래 항목은 데이터 분석 운영에 필요한 핵심 기능 목록입니다. 지표 정의, 원인 분석, 검증 흐름을 중심으로 문서를 구성했습니다.
        </p>

        <ul className="mt-6 space-y-2">
          {sections.map((item) => (
            <li key={item} className="rounded-lg border border-slate-800 bg-slate-900 px-4 py-3 text-sm">
              {item}
            </li>
          ))}
        </ul>

        <div className="mt-6 flex flex-wrap gap-3">
          <Link
            href="/trial"
            className="rounded-xl bg-emerald-400 px-5 py-3 text-sm font-bold text-slate-950 transition hover:bg-emerald-300"
          >
            분석 체험 시작
          </Link>
          <Link
            href="/"
            className="rounded-xl border border-slate-700 px-5 py-3 text-sm font-semibold transition hover:border-slate-500"
          >
            홈으로 돌아가기
          </Link>
        </div>
      </div>
    </main>
  );
}

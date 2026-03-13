import Link from "next/link";

export default function ContactPage() {
  return (
    <main className="min-h-screen bg-slate-950 px-6 py-12 text-slate-100 sm:px-10">
      <div className="mx-auto max-w-3xl rounded-2xl border border-slate-800 bg-slate-900/70 p-8">
        <p className="text-xs font-semibold tracking-[0.2em] text-amber-200">ANALYSIS SETUP</p>
        <h1 className="mt-3 text-3xl font-black">분석 세팅 상담</h1>
        <p className="mt-4 text-sm leading-7 text-slate-300 sm:text-base">
          데이터 소스 연결, KPI 정의, 이벤트 설계, 리포트 주기 설정까지 분석 운영 기준으로 초기 세팅을 함께 정리합니다.
        </p>
        <div className="mt-6 flex flex-wrap gap-3">
          <Link
            href="/trial"
            className="rounded-xl bg-amber-300 px-5 py-3 text-sm font-bold text-slate-950 transition hover:bg-amber-200"
          >
            분석 체험 보기
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

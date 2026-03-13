"use client";

import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { trackEvent } from "../../../lib/tracking";

type DatabaseType = "postgresql" | "mysql" | "mssql";

type ConnectionForm = {
  dbType: DatabaseType;
  host: string;
  port: string;
  dbName: string;
  username: string;
  password: string;
  schema: string;
  ssl: boolean;
};

const defaultPorts: Record<DatabaseType, string> = {
  postgresql: "5432",
  mysql: "3306",
  mssql: "1433",
};

const defaultSchemas: Record<DatabaseType, string> = {
  postgresql: "public",
  mysql: "",
  mssql: "dbo",
};

const initialState: ConnectionForm = {
  dbType: "postgresql",
  host: "",
  port: defaultPorts.postgresql,
  dbName: "",
  username: "",
  password: "",
  schema: defaultSchemas.postgresql,
  ssl: true,
};

export default function ConnectDbPage() {
  const router = useRouter();
  const [form, setForm] = useState<ConnectionForm>(initialState);
  const [isTesting, setIsTesting] = useState(false);
  const [status, setStatus] = useState<"idle" | "success" | "error">("idle");
  const [message, setMessage] = useState("연결 정보를 입력하고 테스트를 실행하세요.");

  const connectionPreview = useMemo(() => {
    const user = form.username || "user";
    const host = form.host || "host";
    const port = form.port || defaultPorts[form.dbType];
    const dbName = form.dbName || "database";
    return `${form.dbType}://${user}:******@${host}:${port}/${dbName}`;
  }, [form]);

  const setField = <K extends keyof ConnectionForm>(key: K, value: ConnectionForm[K]) => {
    setForm((prev) => {
      if (key === "dbName") {
        const dbName = String(value);
        if (prev.dbType === "mysql" && (!prev.schema || prev.schema === prev.dbName || prev.schema === "public")) {
          return { ...prev, dbName, schema: dbName };
        }
      }
      return { ...prev, [key]: value };
    });
  };

  const onDbTypeChange = (value: DatabaseType) => {
    setForm((prev) => ({
      ...prev,
      dbType: value,
      port: defaultPorts[value],
      schema: value === "mysql" ? prev.dbName : defaultSchemas[value],
    }));
  };

  const validateRequired = () => {
    return form.host.trim() && form.port.trim() && form.dbName.trim() && form.username.trim();
  };

  const testConnection = async () => {
    trackEvent("db_connection_test_click", {
      page: "trial_connect_db",
      db_type: form.dbType,
      ssl: form.ssl,
    });

    if (!validateRequired()) {
      setStatus("error");
      setMessage("필수 항목(Host, Port, Database, Username)을 입력해 주세요.");
      trackEvent("db_connection_test_result", {
        page: "trial_connect_db",
        result: "validation_error",
      });
      return;
    }

    setIsTesting(true);
    setStatus("idle");
    setMessage("연결 테스트를 실행 중입니다...");

    try {
      const response = await fetch("/api/db/test-connection", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(form),
      });

      const data = (await response.json()) as {
        ok: boolean;
        message: string;
        latencyMs?: number;
      };

      if (response.ok && data.ok) {
        setStatus("success");
        setMessage(`${data.message} (${data.latencyMs ?? 0}ms)`);
        trackEvent("db_connection_test_result", {
          page: "trial_connect_db",
          result: "success",
          db_type: form.dbType,
          latency_ms: data.latencyMs ?? 0,
        });
      } else {
        setStatus("error");
        setMessage(data.message || "연결 테스트 실패: 설정을 확인해 주세요.");
        trackEvent("db_connection_test_result", {
          page: "trial_connect_db",
          result: "failed",
          db_type: form.dbType,
        });
      }
    } catch {
      setStatus("error");
      setMessage("연결 테스트 실패: 네트워크 또는 서버 상태를 확인해 주세요.");
      trackEvent("db_connection_test_result", {
        page: "trial_connect_db",
        result: "request_error",
        db_type: form.dbType,
      });
    } finally {
      setIsTesting(false);
    }
  };

  const moveToDashboard = () => {
    if (status !== "success") {
      setMessage("먼저 연결 테스트를 성공시킨 뒤 대시보드로 이동해 주세요.");
      return;
    }

    const payload = {
      ...form,
      savedAt: Date.now(),
    };

    sessionStorage.setItem("pago-db-connection", JSON.stringify(payload));

    trackEvent("db_dashboard_navigate", {
      page: "trial_connect_db",
      db_type: form.dbType,
    });

    router.push("/trial/dashboard");
  };

  return (
    <main className="min-h-screen bg-slate-950 px-6 py-10 text-slate-100 sm:px-10 lg:px-12">
      <div className="mx-auto grid w-full max-w-6xl gap-5 lg:grid-cols-[1.1fr_0.9fr]">
        <section className="reveal rounded-2xl border border-slate-800 bg-slate-900/70 p-6 sm:p-7">
          <p className="text-xs font-semibold tracking-[0.2em] text-emerald-300">DATA SOURCE SETUP</p>
          <h1 className="mt-3 text-3xl font-black">데이터베이스 커넥션 연결</h1>
          <p className="mt-3 text-sm leading-7 text-slate-300 sm:text-base">
            분석 체험을 위해 조회 전용 계정으로 연결하는 것을 권장합니다. 비밀번호는 화면에서 마스킹되며,
            실제 운영에서는 서버에서 암호화 저장 방식을 적용해야 합니다.
          </p>

          <div className="mt-6 grid gap-4 sm:grid-cols-2">
            <label className="space-y-2">
              <span className="text-xs font-semibold text-slate-300">DB Type</span>
              <select
                value={form.dbType}
                onChange={(event) => onDbTypeChange(event.target.value as DatabaseType)}
                className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-sm outline-none transition focus:border-emerald-300"
              >
                <option value="postgresql">PostgreSQL</option>
                <option value="mysql">MySQL</option>
                <option value="mssql">MS SQL Server</option>
              </select>
            </label>

            <label className="space-y-2">
              <span className="text-xs font-semibold text-slate-300">Schema</span>
              <input
                value={form.schema}
                onChange={(event) => setField("schema", event.target.value)}
                placeholder={defaultSchemas[form.dbType] || "(optional)"}
                className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-sm outline-none transition focus:border-emerald-300"
              />
            </label>

            <label className="space-y-2 sm:col-span-2">
              <span className="text-xs font-semibold text-slate-300">Host</span>
              <input
                value={form.host}
                onChange={(event) => setField("host", event.target.value)}
                placeholder="analytics-db.company.local"
                className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-sm outline-none transition focus:border-emerald-300"
              />
            </label>

            <label className="space-y-2">
              <span className="text-xs font-semibold text-slate-300">Port</span>
              <input
                value={form.port}
                onChange={(event) => setField("port", event.target.value)}
                placeholder="5432"
                className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-sm outline-none transition focus:border-emerald-300"
              />
            </label>

            <label className="space-y-2">
              <span className="text-xs font-semibold text-slate-300">Database</span>
              <input
                value={form.dbName}
                onChange={(event) => setField("dbName", event.target.value)}
                placeholder="payments_analytics"
                className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-sm outline-none transition focus:border-emerald-300"
              />
            </label>

            <label className="space-y-2">
              <span className="text-xs font-semibold text-slate-300">Username</span>
              <input
                value={form.username}
                onChange={(event) => setField("username", event.target.value)}
                placeholder="readonly_user"
                className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-sm outline-none transition focus:border-emerald-300"
              />
            </label>

            <label className="space-y-2">
              <span className="text-xs font-semibold text-slate-300">Password</span>
              <input
                type="password"
                value={form.password}
                onChange={(event) => setField("password", event.target.value)}
                placeholder="********"
                className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-sm outline-none transition focus:border-emerald-300"
              />
            </label>
          </div>

          <label className="mt-4 inline-flex items-center gap-2 text-sm text-slate-300">
            <input
              type="checkbox"
              checked={form.ssl}
              onChange={(event) => setField("ssl", event.target.checked)}
              className="h-4 w-4 rounded border-slate-700 bg-slate-900"
            />
            SSL 사용
          </label>

          <div className="mt-6 flex flex-wrap gap-3">
            <button
              type="button"
              onClick={testConnection}
              disabled={isTesting}
              className="rounded-xl bg-emerald-400 px-5 py-3 text-sm font-bold text-slate-950 transition hover:bg-emerald-300 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {isTesting ? "테스트 중..." : "연결 테스트"}
            </button>
            <button
              type="button"
              onClick={moveToDashboard}
              disabled={status !== "success"}
              className="rounded-xl border border-emerald-400/60 px-5 py-3 text-sm font-bold text-emerald-300 transition hover:bg-emerald-400/10 disabled:cursor-not-allowed disabled:opacity-60"
            >
              분석 대시보드 이동
            </button>
            <Link
              href="/trial"
              className="rounded-xl border border-slate-700 px-5 py-3 text-sm font-semibold transition hover:border-slate-500"
            >
              체험 페이지로 돌아가기
            </Link>
          </div>
        </section>

        <aside className="reveal rounded-2xl border border-slate-800 bg-slate-900/70 p-6 sm:p-7">
          <h2 className="text-lg font-bold">연결 미리보기</h2>
          <p className="mt-2 text-xs text-slate-400">실제 비밀번호는 숨김 처리되어 표시됩니다.</p>

          <pre className="mt-4 overflow-x-auto rounded-xl border border-slate-800 bg-slate-950 p-3 text-xs text-emerald-300">
            {connectionPreview}
          </pre>

          <div
            className={`mt-4 rounded-xl border p-3 text-sm ${
              status === "success"
                ? "border-emerald-400/40 bg-emerald-400/10 text-emerald-200"
                : status === "error"
                  ? "border-rose-400/40 bg-rose-400/10 text-rose-200"
                  : "border-slate-700 bg-slate-900 text-slate-300"
            }`}
          >
            {message}
          </div>

          <div className="mt-5 space-y-2 text-xs text-slate-400">
            <p>권장 설정</p>
            <p>- 분석 전용 Read-only 계정 사용</p>
            <p>- 접근 가능한 IP 화이트리스트 적용</p>
            <p>- 운영 DB 부하를 고려해 replica 연결 권장</p>
          </div>

          <div className="mt-6 rounded-xl border border-slate-800 bg-slate-950 p-4 text-xs text-slate-400">
            연결 테스트 성공 후 분석 대시보드로 이동하면 테이블 목록을 자동으로 조회합니다.
          </div>
        </aside>
      </div>
    </main>
  );
}

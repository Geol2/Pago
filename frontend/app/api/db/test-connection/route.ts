import { NextResponse } from "next/server";
import { Client as PgClient } from "pg";
import mysql from "mysql2/promise";
import sql from "mssql";

type DatabaseType = "postgresql" | "mysql" | "mssql";

type TestConnectionRequest = {
    dbType: DatabaseType;
    host: string;
    port: string;
    dbName: string;
    username: string;
    password?: string;
    schema?: string;
    ssl?: boolean;
};

const CONNECTION_TIMEOUT_MS = 8000;

function validatePayload(payload: TestConnectionRequest): string | null {
    if (!payload.dbType || !payload.host || !payload.port || !payload.dbName || !payload.username) {
        return "필수 필드가 누락되었습니다.";
    }

    const port = Number(payload.port);
    if (!Number.isInteger(port) || port <= 0 || port > 65535) {
        return "유효한 포트 번호를 입력해 주세요.";
    }

    return null;
}

function getErrorMessage(error: unknown): string {
    if (error instanceof Error) {
        return error.message;
    }
    return "알 수 없는 연결 오류가 발생했습니다.";
}

async function testPostgres(payload: TestConnectionRequest): Promise<void> {
    const client = new PgClient({
        host: payload.host,
        port: Number(payload.port),
        database: payload.dbName,
        user: payload.username,
        password: payload.password,
        ssl: payload.ssl ? { rejectUnauthorized: false } : false,
        connectionTimeoutMillis: CONNECTION_TIMEOUT_MS,
    });

    try {
        await client.connect();
        await client.query("SELECT 1");
    } finally {
        await client.end().catch(() => undefined);
    }
}

async function testMysql(payload: TestConnectionRequest): Promise<void> {
    const connection = await mysql.createConnection({
        host: payload.host,
        port: Number(payload.port),
        database: payload.dbName,
        user: payload.username,
        password: payload.password,
        ssl: payload.ssl ? {} : undefined,
        connectTimeout: CONNECTION_TIMEOUT_MS,
    });

    try {
        await connection.query("SELECT 1");
    } finally {
        await connection.end().catch(() => undefined);
    }
}

async function testMssql(payload: TestConnectionRequest): Promise<void> {
    const pool = new sql.ConnectionPool({
        server: payload.host,
        port: Number(payload.port),
        database: payload.dbName,
        user: payload.username,
        password: payload.password,
        options: {
        encrypt: Boolean(payload.ssl),
        trustServerCertificate: true,
        },
        connectionTimeout: CONNECTION_TIMEOUT_MS,
        requestTimeout: CONNECTION_TIMEOUT_MS,
    });

    await pool.connect();

    try {
        await pool.request().query("SELECT 1");
    } finally {
        await pool.close();
    }
}

export async function POST(req: Request) {
    let payload: TestConnectionRequest;

    try {
        payload = (await req.json()) as TestConnectionRequest;
    } catch {
        return NextResponse.json(
        { ok: false, message: "요청 형식이 올바르지 않습니다." },
        { status: 400 },
        );
    }

    const validationError = validatePayload(payload);
    if (validationError) {
        return NextResponse.json({ ok: false, message: validationError }, { status: 400 });
    }

  const start = Date.now();

    try {
        if (payload.dbType === "postgresql") {
        await testPostgres(payload);
        } else if (payload.dbType === "mysql") {
        await testMysql(payload);
        } else {
        await testMssql(payload);
        }

        return NextResponse.json({
        ok: true,
        message: "연결 테스트 성공: DB 핸드셰이크 및 쿼리 확인 완료.",
        latencyMs: Date.now() - start,
        });
    } catch (error) {
        return NextResponse.json(
        {
            ok: false,
            message: `연결 테스트 실패: ${getErrorMessage(error)}`,
            latencyMs: Date.now() - start,
        },
        { status: 500 },
        );
    }
}

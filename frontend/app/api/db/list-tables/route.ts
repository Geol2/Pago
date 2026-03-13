import { NextResponse } from "next/server";
import { Client as PgClient } from "pg";
import mysql from "mysql2/promise";
import sql from "mssql";

type DatabaseType = "postgresql" | "mysql" | "mssql";

type ListTablesRequest = {
    dbType: DatabaseType;
    host: string;
    port: string;
    dbName: string;
    username: string;
    password?: string;
    schema?: string;
    ssl?: boolean;
};

type TableRow = {
    schema: string;
    name: string;
};

const CONNECTION_TIMEOUT_MS = 8000;

function validatePayload(payload: ListTablesRequest): string | null {
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
    return "테이블 조회 중 알 수 없는 오류가 발생했습니다.";
}

async function listPostgresTables(payload: ListTablesRequest): Promise<TableRow[]> {
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

        const requestedSchema = (payload.schema || "").trim();

        const queryBySchema = `
        SELECT table_schema, table_name
        FROM information_schema.tables
        WHERE table_type = 'BASE TABLE'
            AND table_schema = $1
        ORDER BY table_name ASC
        `;

        const queryAllUserSchemas = `
        SELECT table_schema, table_name
        FROM information_schema.tables
        WHERE table_type = 'BASE TABLE'
            AND table_schema NOT IN ('pg_catalog', 'information_schema')
        ORDER BY table_schema ASC, table_name ASC
        `;

        if (requestedSchema) {
        const filtered = await client.query<{ table_schema: string; table_name: string }>(queryBySchema, [requestedSchema]);
        if (filtered.rows.length > 0) {
            return filtered.rows.map((row) => ({ schema: row.table_schema, name: row.table_name }));
        }
        }

        const fallback = await client.query<{ table_schema: string; table_name: string }>(queryAllUserSchemas);
        return fallback.rows.map((row) => ({ schema: row.table_schema, name: row.table_name }));
    } finally {
        await client.end().catch(() => undefined);
    }
}

async function listMysqlTables(payload: ListTablesRequest): Promise<TableRow[]> {
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
        // In MySQL, table_schema is effectively the database name.
        const schema = payload.dbName.trim();
        const [rows] = await connection.query<mysql.RowDataPacket[]>(
        `
        SELECT table_schema, table_name
        FROM information_schema.tables
        WHERE table_type = 'BASE TABLE'
            AND table_schema = ?
        ORDER BY table_name ASC
        `,
        [schema],
        );

        return rows.map((row) => ({
        schema: String(row.table_schema),
        name: String(row.table_name),
        }));
    } finally {
        await connection.end().catch(() => undefined);
    }
}

async function listMssqlTables(payload: ListTablesRequest): Promise<TableRow[]> {
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
        const requestedSchema = (payload.schema || "").trim();

        const bySchemaRequest = pool.request();
        bySchemaRequest.input("schema", sql.NVarChar, requestedSchema || "dbo");

        const bySchemaResult = await bySchemaRequest.query<{
        table_schema: string;
        table_name: string;
        }>(`
        SELECT TABLE_SCHEMA AS table_schema, TABLE_NAME AS table_name
        FROM INFORMATION_SCHEMA.TABLES
        WHERE TABLE_TYPE = 'BASE TABLE'
            AND TABLE_SCHEMA = @schema
        ORDER BY TABLE_NAME ASC
        `);

        if (requestedSchema && bySchemaResult.recordset.length > 0) {
        return bySchemaResult.recordset.map((row) => ({ schema: row.table_schema, name: row.table_name }));
        }

        if (!requestedSchema && bySchemaResult.recordset.length > 0) {
        return bySchemaResult.recordset.map((row) => ({ schema: row.table_schema, name: row.table_name }));
        }

        const allSchemasResult = await pool.request().query<{
        table_schema: string;
        table_name: string;
        }>(`
        SELECT TABLE_SCHEMA AS table_schema, TABLE_NAME AS table_name
        FROM INFORMATION_SCHEMA.TABLES
        WHERE TABLE_TYPE = 'BASE TABLE'
            AND TABLE_SCHEMA NOT IN ('INFORMATION_SCHEMA', 'sys')
        ORDER BY TABLE_SCHEMA ASC, TABLE_NAME ASC
        `);

        return allSchemasResult.recordset.map((row) => ({ schema: row.table_schema, name: row.table_name }));
    } finally {
        await pool.close();
    }
}

export async function POST(req: Request) {
    let payload: ListTablesRequest;

    try {
        payload = (await req.json()) as ListTablesRequest;
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

    try {
        const tables =
        payload.dbType === "postgresql"
            ? await listPostgresTables(payload)
            : payload.dbType === "mysql"
            ? await listMysqlTables(payload)
            : await listMssqlTables(payload);

        return NextResponse.json({
        ok: true,
        tables,
        count: tables.length,
        message: tables.length > 0 ? "테이블 목록 조회 완료" : "조회된 테이블이 없습니다.",
        });
    } catch (error) {
        return NextResponse.json(
        {
            ok: false,
            message: `테이블 조회 실패: ${getErrorMessage(error)}`,
        },
        { status: 500 },
        );
    }
}

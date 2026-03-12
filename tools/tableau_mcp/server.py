"""
Tableau Server MCP Server
将 TableauServerClientV2 的核心功能暴露为 MCP Tools，
供 AI Agent（如 Cursor、Claude Desktop 等）通过 MCP 协议调用。

启动方式:
    python server.py                         # stdio 模式（默认，用于 Cursor/Claude Desktop）
    python server.py --transport sse         # SSE 模式（用于远程/Web 场景）
"""

import argparse
import base64
import json
import logging
import os

from mcp.server.fastmcp import FastMCP

from tableau_client_v2 import TableauServerClientV2, ProductType, ConfigManager, TableauConfig

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s - %(message)s")
logger = logging.getLogger("tableau_mcp")

# ==================== MCP Server 定义 ====================

mcp = FastMCP(
    "Tableau Server",
    instructions="通过 MCP 协议操作 Tableau Server REST API：查询资源、获取视图截图/数据、刷新数据源、管理作业等",
)

# ==================== 客户端生命周期管理 ====================

_clients: dict[str, TableauServerClientV2] = {}


def _override_config_from_env():
    """从环境变量覆盖硬编码的服务器配置（可选）"""
    for product in ProductType:
        prefix = f"TABLEAU_{product.name}_"
        server_url = os.environ.get(f"{prefix}SERVER_URL")
        token_name = os.environ.get(f"{prefix}TOKEN_NAME")
        token_value = os.environ.get(f"{prefix}TOKEN_VALUE")
        if server_url and token_name and token_value:
            ConfigManager.add_config(product, TableauConfig(
                server_url=server_url,
                token_name=token_name,
                token_value=token_value,
            ))
            logger.info(f"已从环境变量加载 {product.name} 配置")


_override_config_from_env()


def _get_client(product: str = "Aries") -> TableauServerClientV2:
    """
    懒初始化客户端。首次获取时自动登录，后续复用。
    已有的 RetryDecorator 会在 token 过期时自动重新登录。
    """
    if product not in _clients:
        client = TableauServerClientV2(product)
        client.auth_manager.sign_in()
        _clients[product] = client
        logger.info(f"已初始化并登录 {product} 客户端")
    return _clients[product]


def _df_to_markdown(df, max_rows: int = 200) -> str:
    """将 DataFrame 转为 Markdown 表格，截断超长结果"""
    if df.empty:
        return "（空结果集）"
    truncated = len(df) > max_rows
    text = df.head(max_rows).to_markdown(index=False)
    if truncated:
        text += f"\n\n... 共 {len(df)} 行，仅展示前 {max_rows} 行"
    return text


# ==================== MCP Tools ====================


@mcp.tool()
def get_resource_id(resource_type: str, resource_name: str, product: str = "Aries") -> str:
    """
    根据名称查找 Tableau 资源的 ID。

    Args:
        resource_type: 资源类型，可选值: workbook / datasource / view
        resource_name: 资源名称（精确匹配）
        product: 产品线，可选值: Aries / ClassUpOld / ClassUp，默认 Aries
    """
    client = _get_client(product)
    resource_id = client.get_resource_id_by_name(resource_type, resource_name)
    return json.dumps({"resource_type": resource_type, "resource_name": resource_name, "resource_id": resource_id},
                      ensure_ascii=False)


@mcp.tool()
def get_view_image(view_id: str, product: str = "Aries",
                   high_resolution: bool = True,
                   filters: dict | None = None) -> str:
    """
    获取 Tableau 视图的截图（PNG 格式），返回 base64 编码字符串。

    Args:
        view_id: 视图 ID
        product: 产品线，默认 Aries
        high_resolution: 是否高清，默认 True
        filters: 视图过滤器，如 {"region": "华北"}
    """
    client = _get_client(product)
    image_bytes = client.get_view_image_by_id(view_id, high_resolution=high_resolution, filters=filters)
    b64 = base64.b64encode(image_bytes).decode("ascii")
    return json.dumps({
        "view_id": view_id,
        "format": "png",
        "size_kb": round(len(image_bytes) / 1024, 2),
        "base64": b64,
    })


@mcp.tool()
def get_view_data(view_id: str, product: str = "Aries",
                  filters: dict | None = None,
                  header_rows: int = 1) -> str:
    """
    获取 Tableau 视图的交叉表数据，返回 Markdown 表格。

    Args:
        view_id: 视图 ID
        product: 产品线，默认 Aries
        filters: 视图过滤器
        header_rows: 表头行数，默认 1
    """
    client = _get_client(product)
    df = client.populate_view_excel(view_id, filters=filters, header_rows=header_rows)
    return _df_to_markdown(df)


@mcp.tool()
def extract_datasources(datasource_id: str | None = None, product: str = "Aries") -> str:
    """
    提取数据源元信息（连接地址、SQL、Owner 等），返回 Markdown 表格。
    不传 datasource_id 则提取全部数据源（耗时较长）。

    Args:
        datasource_id: 指定数据源 ID，为空则提取全部
        product: 产品线，默认 Aries
    """
    client = _get_client(product)
    df = client.extract_datasource(datasource_id)
    return _df_to_markdown(df)


@mcp.tool()
def submit_datasource_refresh(datasource_id: str, product: str = "Aries") -> str:
    """
    提交数据源刷新作业（异步），返回 job_id 用于后续查询状态。

    Args:
        datasource_id: 数据源 ID
        product: 产品线，默认 Aries
    """
    client = _get_client(product)
    job_id = client.submit_datasource_refresh_job(datasource_id)
    return json.dumps({"datasource_id": datasource_id, "job_id": job_id}, ensure_ascii=False)


@mcp.tool()
def get_job_status(job_id: str, product: str = "Aries") -> str:
    """
    查询 Tableau 作业（Job）的执行状态。finish_code: 0=成功, 1=失败, 2=取消。

    Args:
        job_id: 作业 ID
        product: 产品线，默认 Aries
    """
    client = _get_client(product)
    job = client.get_job_by_id(job_id)
    return json.dumps(job, ensure_ascii=False, default=str)


@mcp.tool()
def wait_datasource_refresh(job_id: str, product: str = "Aries") -> str:
    """
    阻塞等待数据源刷新作业完成（最长 1 小时），返回最终状态。
    注意：这是一个长耗时操作。

    Args:
        job_id: 刷新作业 ID（由 submit_datasource_refresh 返回）
        product: 产品线，默认 Aries
    """
    client = _get_client(product)
    client.wait_datasource_refresh(job_id)
    job = client.get_job_by_id(job_id)
    return json.dumps(job, ensure_ascii=False, default=str)


@mcp.tool()
def download_workbook(workbook_id: str, include_extract: bool = True, product: str = "Aries") -> str:
    """
    下载 Tableau 工作簿到本地，返回文件保存路径。

    Args:
        workbook_id: 工作簿 ID
        include_extract: 是否包含数据提取（True 下载 .twbx，False 下载 .twb）
        product: 产品线，默认 Aries
    """
    client = _get_client(product)
    path = client.download_workbook(workbook_id, include_extract)
    return json.dumps({"workbook_id": workbook_id, "saved_path": path}, ensure_ascii=False)


@mcp.tool()
def get_workbook_images(workbook_id: str, product: str = "Aries") -> str:
    """
    获取工作簿下所有视图的截图，返回 base64 编码的 PNG 图片列表。

    Args:
        workbook_id: 工作簿 ID
        product: 产品线，默认 Aries
    """
    client = _get_client(product)
    images = client.workbooks.get_workbook_images(workbook_id)
    result = []
    for i, img_bytes in enumerate(images):
        result.append({
            "index": i,
            "size_kb": round(len(img_bytes) / 1024, 2),
            "base64": base64.b64encode(img_bytes).decode("ascii"),
        })
    return json.dumps({"workbook_id": workbook_id, "image_count": len(result), "images": result})


@mcp.tool()
def backup_workbooks(workbook_id: str | None = None, product: str = "Aries") -> str:
    """
    备份工作簿。不传 workbook_id 则备份全部（耗时极长，谨慎使用）。

    Args:
        workbook_id: 指定工作簿 ID，为空则备份全部
        product: 产品线，默认 Aries
    """
    client = _get_client(product)
    client.backup_workbooks(workbook_id)
    return json.dumps({"status": "completed", "workbook_id": workbook_id or "all"}, ensure_ascii=False)


@mcp.tool()
def extract_jobs(product: str = "Aries",
                 filter_status: str | None = None,
                 filter_job_type: str | None = None,
                 sort_by: str = "completedAt",
                 sort_order: str = "desc") -> str:
    """
    提取 Tableau 后台作业列表（支持过滤和排序），返回 Markdown 表格。

    Args:
        product: 产品线，默认 Aries
        filter_status: 过滤状态，如 Success / Failed / Cancelled / InProgress
        filter_job_type: 过滤作业类型，如 refresh_extracts
        sort_by: 排序字段，如 completedAt / createdAt
        sort_order: 排序方向，asc / desc
    """
    filters = {}
    if filter_status:
        filters["status"] = ("eq", filter_status)
    if filter_job_type:
        filters["jobType"] = ("eq", filter_job_type)

    sorted_by = {sort_by: sort_order} if sort_by else None

    client = _get_client(product)
    df = client.extract_jobs(filters=filters or None, sorted_by=sorted_by)
    return _df_to_markdown(df)


@mcp.tool()
def get_projects(product: str = "Aries") -> str:
    """
    获取 Tableau 项目层级结构。

    Args:
        product: 产品线，默认 Aries
    """
    client = _get_client(product)
    project_tree = client.projects.get_projects()
    rows = []
    for pid, info in project_tree.items():
        rows.append({
            "project_id": pid,
            "name": info["name"],
            "parent_id": info["parent_id"] or "",
            "children_count": len(info["children"]),
        })
    import pandas as pd
    df = pd.DataFrame(rows)
    return _df_to_markdown(df)


# ==================== 入口 ====================

def main():
    parser = argparse.ArgumentParser(description="Tableau Server MCP Server")
    parser.add_argument("--transport", choices=["stdio", "sse"], default="stdio",
                        help="MCP 传输协议 (默认: stdio)")
    parser.add_argument("--port", type=int, default=8000,
                        help="SSE 模式监听端口 (默认: 8000)")
    args = parser.parse_args()

    logger.info(f"启动 Tableau MCP Server，传输协议: {args.transport}")

    if args.transport == "sse":
        mcp.run(transport="sse", sse_params={"port": args.port})
    else:
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()

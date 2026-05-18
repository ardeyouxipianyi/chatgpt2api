"use client";

import { DatabaseBackup, Download, LoaderCircle, Upload } from "lucide-react";
import { useRef, useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import webConfig from "@/constants/common-env";
import { importDataPackage, type BackupInclude } from "@/lib/api";
import { getStoredAuthKey } from "@/store/auth";

const transferItems: Array<{ key: keyof BackupInclude; label: string; note: string }> = [
  { key: "config", label: "系统配置", note: "基础设置、管理员密码等" },
  { key: "accounts_snapshot", label: "账号池", note: "所有账号与额度状态" },
  { key: "auth_keys_snapshot", label: "用户密钥", note: "普通用户访问密钥" },
  { key: "image_tasks", label: "图片任务", note: "画图任务记录" },
  { key: "image_canvas", label: "画布项目", note: "画布节点与连接关系" },
  { key: "images", label: "生成图片", note: "本地生成图片与标签" },
  { key: "logs", label: "运行日志", note: "调用日志与账号事件" },
  { key: "register", label: "注册配置", note: "注册模块配置" },
  { key: "cpa", label: "CPA 配置", note: "CPA 连接配置" },
  { key: "sub2api", label: "Sub2API 配置", note: "Sub2API 连接配置" },
];

const defaultInclude: BackupInclude = {
  config: true,
  register: true,
  cpa: true,
  sub2api: true,
  logs: true,
  image_tasks: true,
  image_canvas: true,
  accounts_snapshot: true,
  auth_keys_snapshot: true,
  images: false,
};

function getFilenameFromContentDisposition(value: string | null) {
  const header = String(value || "").trim();
  const utf8Match = header.match(/filename\*\s*=\s*UTF-8''([^;]+)/i);
  if (utf8Match?.[1]) {
    try {
      return decodeURIComponent(utf8Match[1]);
    } catch {
      return utf8Match[1];
    }
  }
  const plainMatch = header.match(/filename\s*=\s*"?([^";]+)"?/i);
  return plainMatch?.[1] || "";
}

export function DataTransferCard() {
  const inputRef = useRef<HTMLInputElement | null>(null);
  const [include, setInclude] = useState<BackupInclude>(defaultInclude);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isExporting, setIsExporting] = useState(false);
  const [isImporting, setIsImporting] = useState(false);

  const selectedCount = transferItems.filter((item) => include[item.key]).length;

  const setAll = (value: boolean) => {
    setInclude((current) => {
      const next = { ...current };
      transferItems.forEach((item) => {
        next[item.key] = value;
      });
      return next;
    });
  };

  const toggle = (key: keyof BackupInclude, value: boolean) => {
    setInclude((current) => ({ ...current, [key]: value }));
  };

  const handleExport = async () => {
    if (selectedCount === 0) {
      toast.error("请至少选择一类要导出的数据");
      return;
    }
    setIsExporting(true);
    try {
      const authKey = await getStoredAuthKey();
      if (!authKey) {
        toast.error("当前登录已失效，请重新登录后再导出");
        return;
      }
      const response = await fetch(`${webConfig.apiUrl.replace(/\/$/, "")}/api/data/export`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${authKey}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ include }),
      });
      if (!response.ok) {
        const data = await response.json().catch(() => null) as { detail?: { error?: string }; error?: string } | null;
        throw new Error(data?.detail?.error || data?.error || "导出失败");
      }
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = getFilenameFromContentDisposition(response.headers.get("Content-Disposition")) || "chatgpt2api-data.tar.gz";
      document.body.append(anchor);
      anchor.click();
      anchor.remove();
      window.URL.revokeObjectURL(url);
      toast.success("数据导出已开始下载");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "导出失败");
    } finally {
      setIsExporting(false);
    }
  };

  const handleImport = async () => {
    if (selectedCount === 0) {
      toast.error("请至少选择一类要导入的数据");
      return;
    }
    if (!selectedFile) {
      toast.error("请先选择导入文件");
      return;
    }
    setIsImporting(true);
    try {
      const data = await importDataPackage(selectedFile, include);
      const imported = data.result.imported?.join("、") || "无";
      toast.success(`导入完成：${imported}`);
      if (include.config || include.auth_keys_snapshot) {
        toast.info("如果导入了系统配置或用户密钥，建议刷新页面后继续操作");
      }
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "导入失败");
    } finally {
      setIsImporting(false);
    }
  };

  return (
    <Card className="rounded-2xl border-white/80 bg-white/90 shadow-sm">
      <CardContent className="space-y-5 p-6">
        <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
          <div className="flex items-center gap-3">
            <div className="flex size-10 items-center justify-center rounded-xl bg-stone-950 text-white">
              <DatabaseBackup className="size-4" />
            </div>
            <div>
              <h2 className="text-base font-semibold text-stone-950">配置数据导入导出</h2>
              <p className="mt-1 text-sm text-stone-500">手动迁移当前程序数据，可选择是否包含生成图片。</p>
            </div>
          </div>
          <div className="flex gap-2">
            <Button type="button" variant="outline" className="h-9 rounded-xl border-stone-200 bg-white px-4 text-stone-700" onClick={() => setAll(true)}>
              全选
            </Button>
            <Button type="button" variant="outline" className="h-9 rounded-xl border-stone-200 bg-white px-4 text-stone-700" onClick={() => setAll(false)}>
              清空
            </Button>
          </div>
        </div>

        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {transferItems.map((item) => (
            <label key={item.key} className="flex items-start gap-3 rounded-xl border border-stone-200 bg-white px-4 py-3 text-sm text-stone-700">
              <Checkbox checked={Boolean(include[item.key])} onCheckedChange={(checked) => toggle(item.key, Boolean(checked))} />
              <span>
                <span className="block font-medium text-stone-800">{item.label}</span>
                <span className="mt-1 block text-xs text-stone-500">{item.note}</span>
              </span>
            </label>
          ))}
        </div>

        <div className="grid gap-3 rounded-xl border border-stone-200 bg-stone-50 px-4 py-4 md:grid-cols-[1fr_auto_auto] md:items-center">
          <input
            ref={inputRef}
            type="file"
            accept=".tar.gz,.gz,application/gzip,application/x-gzip"
            className="hidden"
            onChange={(event) => setSelectedFile(event.target.files?.[0] ?? null)}
          />
          <button type="button" className="truncate rounded-xl border border-stone-200 bg-white px-4 py-2 text-left text-sm text-stone-600" onClick={() => inputRef.current?.click()}>
            {selectedFile ? selectedFile.name : "选择要导入的数据包"}
          </button>
          <Button type="button" variant="outline" className="h-10 rounded-xl border-stone-200 bg-white px-4 text-stone-700" onClick={() => void handleImport()} disabled={isImporting}>
            {isImporting ? <LoaderCircle className="size-4 animate-spin" /> : <Upload className="size-4" />}
            导入所选
          </Button>
          <Button type="button" className="h-10 rounded-xl bg-stone-950 px-4 text-white hover:bg-stone-800" onClick={() => void handleExport()} disabled={isExporting}>
            {isExporting ? <LoaderCircle className="size-4 animate-spin" /> : <Download className="size-4" />}
            导出所选
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using Qros.RunnerLab.Core;

static int Usage()
{
    Console.WriteLine("QROS RunnerLab v3.1 MVP2A");
    Console.WriteLine("Usage:");
    Console.WriteLine("  QROS.RunnerLab.exe selftest [--root <directory>]");
    Console.WriteLine("  QROS.RunnerLab.exe package-release --dist <directory> --out <zip-path>");
    Console.WriteLine("  QROS.RunnerLab.exe mvp2a-selftest [--root <directory>]");
    Console.WriteLine("  QROS.RunnerLab.exe mvp2a [--search-root <directory>] [--data-root <MetaQuotes\\Terminal>] --clone-root <directory> --evidence-root <directory>");
    return 64;
}

static void WriteDurableNew(string path, ReadOnlySpan<byte> bytes)
{
    Directory.CreateDirectory(Path.GetDirectoryName(Path.GetFullPath(path))!);
    using var fs = new FileStream(path, FileMode.CreateNew, FileAccess.Write, FileShare.None, 64 * 1024,
        FileOptions.WriteThrough | FileOptions.SequentialScan);
    fs.Write(bytes);
    fs.Flush(flushToDisk: true);
}

static string? ReadOption(string[] argv, string name)
{
    for (var i = 1; i < argv.Length - 1; i++)
        if (string.Equals(argv[i], name, StringComparison.OrdinalIgnoreCase))
            return argv[i + 1];
    return null;
}

try
{
    if (args.Length == 0) return Usage();

    if (string.Equals(args[0], "package-release", StringComparison.OrdinalIgnoreCase))
    {
        var dist = ReadOption(args, "--dist");
        var output = ReadOption(args, "--out");
        if (dist is null || output is null) return Usage();
        Console.WriteLine("QROS RUNNERLAB — DERIVED RELEASE PACKAGING");
        Console.WriteLine("Scientific state is not modified by this command.");
        var packageReceipt = new ReleasePackager().Package(dist, output);
        Console.WriteLine($"BUNDLE_SHA256 {packageReceipt.Sha256}");
        Console.WriteLine($"BUNDLE_BYTES {packageReceipt.Bytes}");
        Console.WriteLine($"BUNDLE_ENTRIES {packageReceipt.Entries}");
        Console.WriteLine("RUNNERLAB_RELEASE_PACKAGE_PASS");
        return 0;
    }

    if (string.Equals(args[0], "mvp2a-selftest", StringComparison.OrdinalIgnoreCase))
    {
        var mvp2aSelftestRoot = ReadOption(args, "--root") ?? Path.Combine(AppContext.BaseDirectory, "mvp2a_selftest_state");
        Console.WriteLine("QROS RUNNERLAB v3.1 MVP2A — SAFETY SELFTEST");
        Console.WriteLine("NO REAL MT5 LAUNCH | NO Candidate3 | NO TRADES | NO CERT ARM | NO DEPLOYMENT");
        var testReceipt = Mvp2ASelfTests.Run(mvp2aSelftestRoot);
        foreach (var test in testReceipt.Tests)
            Console.WriteLine($"{test.TestId,-40} {(test.Pass ? "PASS" : "FAIL")} {test.Detail}");
        Console.WriteLine(testReceipt.Pass ? "RUNNERLAB_MVP2A_SELFTEST_PASS" : "RUNNERLAB_MVP2A_SELFTEST_FAIL");
        return testReceipt.Pass ? 0 : 1;
    }

    if (string.Equals(args[0], "mvp2a", StringComparison.OrdinalIgnoreCase))
    {
        var cloneRoot = ReadOption(args, "--clone-root");
        var evidenceRoot = ReadOption(args, "--evidence-root");
        if (cloneRoot is null || evidenceRoot is null) return Usage();
        Console.WriteLine("QROS RUNNERLAB v3.1 MVP2A — READ-ONLY DISCOVERY + CLONE PREPARATION");
        Console.WriteLine("NO MT5 LAUNCH | NO Candidate3 | NO TRADES | NO CERT ARM | NO DEPLOYMENT");
        var mvp2aReceipt = new Mvp2AEngine().Run(new Mvp2AOptions(
            ReadOption(args, "--search-root"), ReadOption(args, "--data-root"), cloneRoot, evidenceRoot));
        foreach (var stage in mvp2aReceipt.Stages)
            Console.WriteLine($"{stage.StageId,-58} {(stage.Pass ? "PASS" : "FAIL")} {stage.Detail}");
        Console.WriteLine($"MVP2A_DECISION {mvp2aReceipt.Decision}");
        Console.WriteLine($"MVP2A_PROMOTION_ALLOWED {mvp2aReceipt.PromotionAllowed}");
        Console.WriteLine($"MT5_LAUNCHED {mvp2aReceipt.Mt5Launched}");
        Console.WriteLine($"CANDIDATE3_EXECUTED {mvp2aReceipt.Candidate3Executed}");
        if (mvp2aReceipt.PromotionAllowed) return 0;
        string[] safeStops = ["NO_MT5_FOUND", "AMBIGUOUS_MT5_TARGET", "DATA_ROOT_NOT_MAPPED", "AMBIGUOUS_DATA_ROOT", "PORTABLE_ACTIVE_DATA_UNSAFE", "METAEDITOR64_NOT_FOUND"];
        return safeStops.Contains(mvp2aReceipt.Decision, StringComparer.Ordinal) ? 2 : 3;
    }

    if (!string.Equals(args[0], "selftest", StringComparison.OrdinalIgnoreCase)) return Usage();

    string runnerStateRoot = Path.Combine(AppContext.BaseDirectory, "runnerlab_state");
    for (var i = 1; i < args.Length; i++)
    {
        if (string.Equals(args[i], "--root", StringComparison.OrdinalIgnoreCase) && i + 1 < args.Length)
            runnerStateRoot = args[++i];
        else return Usage();
    }

    runnerStateRoot = Path.GetFullPath(runnerStateRoot);
    Directory.CreateDirectory(runnerStateRoot);
    Console.WriteLine("QROS RUNNERLAB v3.1 MVP1.1 — SELF TEST");
    Console.WriteLine("Candidate3: NOT USED | MT5: NOT ACCESSED | DEPLOYMENT: DISABLED | CERT ARM: IMPOSSIBLE");
    Console.WriteLine($"Root: {runnerStateRoot}");

    var selfTestReceipt = SelfTests.RunAll(runnerStateRoot);
    var runDir = Path.Combine(runnerStateRoot, selfTestReceipt.RunId);
    Directory.CreateDirectory(runDir);
    var receiptPath = Path.Combine(runDir, "SELFTEST_RECEIPT.json");
    var json = JsonSerializer.Serialize(selfTestReceipt, new JsonSerializerOptions { PropertyNamingPolicy = JsonNamingPolicy.SnakeCaseLower, WriteIndented = true });
    var receiptBytes = Encoding.UTF8.GetBytes(json + Environment.NewLine);
    WriteDurableNew(receiptPath, receiptBytes);
    var sha = Convert.ToHexString(SHA256.HashData(receiptBytes)).ToLowerInvariant();
    WriteDurableNew(Path.Combine(runDir, "SELFTEST_RECEIPT.sha256"), Encoding.ASCII.GetBytes($"{sha}  SELFTEST_RECEIPT.json{Environment.NewLine}"));

    foreach (var t in selfTestReceipt.Tests)
        Console.WriteLine($"{t.TestId,-38} {(t.Pass ? "PASS" : "FAIL")} {t.Detail}");
    Console.WriteLine($"RECEIPT_SHA256 {sha}");
    Console.WriteLine(selfTestReceipt.Pass ? "RUNNERLAB_MVP_SELFTEST_PASS" : "RUNNERLAB_MVP_SELFTEST_FAIL");
    return selfTestReceipt.Pass ? 0 : 1;
}
catch (Exception ex)
{
    Console.Error.WriteLine("FATAL " + ex);
    return 99;
}

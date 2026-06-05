#include <ctype.h>
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define LIMIT_N 10000000ULL
#define BIN_WIDTH 10000ULL
#define NBINS 1000
#define SAMPLE_STEP 5000ULL
#define AVG_STEP 10000ULL
#define TOPK 10
#define AVG_POINTS (LIMIT_N / AVG_STEP)

typedef struct {
    int sign;
    const char *digits;
    size_t len;
} NumRef;

typedef struct {
    unsigned long long n;
    unsigned long long d;
} Pair;

static Pair top_d[TOPK];
static unsigned int bin_values[BIN_WIDTH + 8];
static size_t bin_count = 0;
static int current_bin = -1;

static FILE *sample_file;
static FILE *quantile_file;
static FILE *average_file;
static FILE *outlier_file;
static double avg_values[AVG_POINTS + 1];
static unsigned long long avg_ns[AVG_POINTS + 1];

static double sum_x = 0.0, sum_y = 0.0, sum_xx = 0.0, sum_xy = 0.0;
static unsigned long long fit_count = 0;

static int cmp_uint(const void *a, const void *b) {
    unsigned int x = *(const unsigned int *)a;
    unsigned int y = *(const unsigned int *)b;
    return (x > y) - (x < y);
}

static int cmp_numref_abs(NumRef a, NumRef b) {
    while (a.len > 1 && *a.digits == '0') {
        a.digits++;
        a.len--;
    }
    while (b.len > 1 && *b.digits == '0') {
        b.digits++;
        b.len--;
    }
    if (a.len != b.len) return a.len < b.len ? -1 : 1;
    int c = strncmp(a.digits, b.digits, a.len);
    return (c > 0) - (c < 0);
}

static unsigned long long abs_diff_to_ull(NumRef a, NumRef b) {
    int c = cmp_numref_abs(a, b);
    const char *pa;
    const char *pb;
    size_t la, lb;
    if (c >= 0) {
        pa = a.digits;
        la = a.len;
        pb = b.digits;
        lb = b.len;
    } else {
        pa = b.digits;
        la = b.len;
        pb = a.digits;
        lb = a.len;
    }
    unsigned long long result = 0;
    int borrow = 0;
    unsigned long long place = 1;
    while (la || lb) {
        int da = la ? pa[--la] - '0' : 0;
        int db = lb ? pb[--lb] - '0' : 0;
        da -= borrow;
        if (da < db) {
            da += 10;
            borrow = 1;
        } else {
            borrow = 0;
        }
        result += (unsigned long long)(da - db) * place;
        place *= 10;
    }
    return result;
}

static unsigned long long sum_abs_to_ull(NumRef a, NumRef b) {
    size_t ia = a.len, ib = b.len;
    unsigned long long result = 0;
    unsigned long long place = 1;
    int carry = 0;
    while (ia || ib || carry) {
        int da = ia ? a.digits[--ia] - '0' : 0;
        int db = ib ? b.digits[--ib] - '0' : 0;
        int s = da + db + carry;
        result += (unsigned long long)(s % 10) * place;
        carry = s / 10;
        place *= 10;
    }
    return result;
}

static unsigned long long abs_sum_to_ull(NumRef a, NumRef b) {
    if (a.sign == b.sign) return sum_abs_to_ull(a, b);
    return abs_diff_to_ull(a, b);
}

static int parse_coeffs(char *line, NumRef nums[4]) {
    char *p = line;
    for (int i = 0; i < 4; i++) {
        p = strchr(p, '(');
        if (!p) return 0;
        p++;
        nums[i].sign = 1;
        if (*p == '-') {
            nums[i].sign = -1;
            p++;
        }
        if (!isdigit((unsigned char)*p)) return 0;
        nums[i].digits = p;
        while (isdigit((unsigned char)*p)) p++;
        nums[i].len = (size_t)(p - nums[i].digits);
        if (*p != ')') return 0;
    }
    return 1;
}

static void add_top(unsigned long long n, unsigned long long d) {
    int pos = -1;
    for (int i = 0; i < TOPK; i++) {
        if (d > top_d[i].d) {
            pos = i;
            break;
        }
    }
    if (pos < 0) return;
    for (int i = TOPK - 1; i > pos; i--) top_d[i] = top_d[i - 1];
    top_d[pos].n = n;
    top_d[pos].d = d;
}

static double theory_x(unsigned long long n) {
    double ln = log((double)n);
    double lln = log(ln);
    return sqrt(ln * lln);
}

static void flush_bin(void) {
    if (current_bin < 0 || bin_count == 0) return;
    qsort(bin_values, bin_count, sizeof(unsigned int), cmp_uint);
    double sum = 0.0;
    for (size_t i = 0; i < bin_count; i++) sum += bin_values[i];
    unsigned long long lo = (unsigned long long)current_bin * BIN_WIDTH + 1;
    unsigned long long hi = lo + BIN_WIDTH - 1;
    if (hi > LIMIT_N) hi = LIMIT_N;
    unsigned long long mid = (lo + hi) / 2;
    size_t i50 = (size_t)(0.50 * (double)(bin_count - 1));
    size_t i90 = (size_t)(0.90 * (double)(bin_count - 1));
    size_t i99 = (size_t)(0.99 * (double)(bin_count - 1));
    size_t i999 = (size_t)(0.999 * (double)(bin_count - 1));
    fprintf(quantile_file, "%llu %.8f %u %u %u %u %u\n",
            mid, sum / (double)bin_count, bin_values[i50], bin_values[i90],
            bin_values[i99], bin_values[i999], bin_values[bin_count - 1]);
    bin_count = 0;
}

int main(int argc, char **argv) {
    const char *outdir = argc > 1 ? argv[1] : "figures/data";
    char path[512];
    snprintf(path, sizeof(path), "%s/d_sample.dat", outdir);
    sample_file = fopen(path, "w");
    snprintf(path, sizeof(path), "%s/d_quantiles.dat", outdir);
    quantile_file = fopen(path, "w");
    snprintf(path, sizeof(path), "%s/d_average.dat", outdir);
    average_file = fopen(path, "w");
    snprintf(path, sizeof(path), "%s/d_outliers.dat", outdir);
    outlier_file = fopen(path, "w");
    if (!sample_file || !quantile_file || !average_file || !outlier_file) {
        perror("opening output file");
        return 1;
    }

    fprintf(sample_file, "n d\n");
    fprintf(quantile_file, "n mean median p90 p99 p999 max\n");
    fprintf(outlier_file, "n d\n");

    char *line = NULL;
    size_t cap = 0;
    unsigned long long processed = 0, n_seen = 0;
    double cumulative = 0.0;
    while (getline(&line, &cap, stdin) != -1) {
        unsigned long long n = strtoull(line, NULL, 10);
        if (n == 0) continue;
        if (n > LIMIT_N) break;
        NumRef nums[4];
        if (!parse_coeffs(line, nums)) {
            fprintf(stderr, "could not parse line for n=%llu\n", n);
            continue;
        }
        unsigned long long d = abs_sum_to_ull(nums[2], nums[3]);
        int bin = (int)((n - 1) / BIN_WIDTH);
        if (bin != current_bin) {
            flush_bin();
            current_bin = bin;
        }
        bin_values[bin_count++] = (unsigned int)d;
        cumulative += (double)d;
        n_seen++;
        add_top(n, d);
        if (n % SAMPLE_STEP == 0) {
            fprintf(sample_file, "%llu %llu\n", n, d);
        }
        if (n % AVG_STEP == 0) {
            double avg = cumulative / (double)n_seen;
            double x = theory_x(n);
            if (fit_count < AVG_POINTS) {
                avg_ns[fit_count] = n;
                avg_values[fit_count] = avg;
            }
            sum_x += x;
            sum_y += avg;
            sum_xx += x * x;
            sum_xy += x * avg;
            fit_count++;
        }
        processed++;
        if (processed % 1000000ULL == 0) {
            fprintf(stderr, "processed %llu values; n=%llu\n", processed, n);
        }
    }
    flush_bin();

    double denom = (double)fit_count * sum_xx - sum_x * sum_x;
    double slope = denom ? ((double)fit_count * sum_xy - sum_x * sum_y) / denom : 0.0;
    double intercept = fit_count ? (sum_y - slope * sum_x) / (double)fit_count : 0.0;

    fprintf(average_file, "n avg model\n");
    for (unsigned long long i = 0; i < fit_count && i < AVG_POINTS; i++) {
        unsigned long long n = avg_ns[i];
        double avg_model = intercept + slope * theory_x(n);
        fprintf(average_file, "%llu %.12f %.12f\n", n, avg_values[i], avg_model);
    }
    snprintf(path, sizeof(path), "%s/d_fit_params.dat", outdir);
    FILE *fit_file = fopen(path, "w");
    if (fit_file) {
        fprintf(fit_file, "slope intercept\n%.12f %.12f\n", slope, intercept);
        fclose(fit_file);
    }

    for (int i = 0; i < TOPK; i++) {
        fprintf(outlier_file, "%llu %llu\n", top_d[i].n, top_d[i].d);
    }

    free(line);
    fclose(sample_file);
    fclose(quantile_file);
    fclose(average_file);
    fclose(outlier_file);
    fprintf(stderr, "processed %llu values total; slope=%.8f intercept=%.8f\n",
            processed, slope, intercept);
    return 0;
}

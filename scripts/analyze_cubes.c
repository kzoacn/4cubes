#include <ctype.h>
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define TOPK 20

typedef struct {
    unsigned long long n;
    char *line;
    char *d;
    char *h;
    double d_score;
    double h_over_n_score;
} Entry;

typedef struct {
    int sign;
    const char *digits;
    size_t len;
} NumRef;

static Entry top_d[TOPK], top_h[TOPK], top_d_score[TOPK], top_h_over_n[TOPK];

static char *xstrdup(const char *s) {
    char *r = strdup(s);
    if (!r) {
        perror("strdup");
        exit(1);
    }
    return r;
}

static int cmp_decimal(const char *a, const char *b) {
    while (*a == '0' && a[1]) a++;
    while (*b == '0' && b[1]) b++;
    size_t la = strlen(a), lb = strlen(b);
    if (la != lb) return la < lb ? -1 : 1;
    int c = strcmp(a, b);
    return (c > 0) - (c < 0);
}

static char *trim_leading_zeros(char *s) {
    char *p = s;
    while (*p == '0' && p[1]) p++;
    if (p != s) memmove(s, p, strlen(p) + 1);
    return s;
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

static char *numref_abs_string(NumRef a) {
    while (a.len > 1 && *a.digits == '0') {
        a.digits++;
        a.len--;
    }
    char *out = malloc(a.len + 1);
    if (!out) {
        perror("malloc");
        exit(1);
    }
    memcpy(out, a.digits, a.len);
    out[a.len] = '\0';
    return out;
}

static char *add_abs(NumRef a, NumRef b) {
    size_t max = a.len > b.len ? a.len : b.len;
    char *out = calloc(max + 2, 1);
    if (!out) {
        perror("calloc");
        exit(1);
    }
    int carry = 0;
    size_t ia = a.len, ib = b.len, k = max + 1;
    out[k] = '\0';
    while (ia || ib || carry) {
        int da = ia ? a.digits[--ia] - '0' : 0;
        int db = ib ? b.digits[--ib] - '0' : 0;
        int s = da + db + carry;
        out[--k] = (char)('0' + (s % 10));
        carry = s / 10;
    }
    char *res = xstrdup(out + k);
    free(out);
    return trim_leading_zeros(res);
}

static char *sub_abs_ge(NumRef a, NumRef b) {
    char *out = calloc(a.len + 1, 1);
    if (!out) {
        perror("calloc");
        exit(1);
    }
    int borrow = 0;
    size_t ia = a.len, ib = b.len, k = a.len;
    out[k] = '\0';
    while (k > 0) {
        int da = a.digits[--ia] - '0' - borrow;
        int db = ib ? b.digits[--ib] - '0' : 0;
        if (da < db) {
            da += 10;
            borrow = 1;
        } else {
            borrow = 0;
        }
        out[--k] = (char)('0' + (da - db));
    }
    return trim_leading_zeros(out);
}

static char *abs_sum(NumRef a, NumRef b) {
    if (a.sign == b.sign) return add_abs(a, b);
    int c = cmp_numref_abs(a, b);
    if (c == 0) return xstrdup("0");
    return c > 0 ? sub_abs_ge(a, b) : sub_abs_ge(b, a);
}

static double decimal_log10(const char *s) {
    while (*s == '0' && s[1]) s++;
    size_t len = strlen(s);
    size_t take = len < 16 ? len : 16;
    char buf[17];
    memcpy(buf, s, take);
    buf[take] = '\0';
    double lead = atof(buf);
    return (double)(len - take) + log10(lead);
}

static double decimal_to_double_limited(const char *s) {
    if (strlen(s) > 18) return 1e18;
    return atof(s);
}

static void free_entry(Entry *e) {
    free(e->line);
    free(e->d);
    free(e->h);
    memset(e, 0, sizeof(*e));
}

static void copy_entry(Entry *dst, const Entry *src) {
    dst->n = src->n;
    dst->line = xstrdup(src->line);
    dst->d = xstrdup(src->d);
    dst->h = xstrdup(src->h);
    dst->d_score = src->d_score;
    dst->h_over_n_score = src->h_over_n_score;
}

static void maybe_insert_decimal(Entry arr[TOPK], const Entry *cur, int by_h) {
    int pos = -1;
    for (int i = 0; i < TOPK; i++) {
        if (!arr[i].line) {
            pos = i;
            break;
        }
        int cmp = cmp_decimal(by_h ? cur->h : cur->d, by_h ? arr[i].h : arr[i].d);
        if (cmp > 0) {
            pos = i;
            break;
        }
    }
    if (pos < 0) return;
    free_entry(&arr[TOPK - 1]);
    for (int i = TOPK - 1; i > pos; i--) arr[i] = arr[i - 1];
    memset(&arr[pos], 0, sizeof(arr[pos]));
    copy_entry(&arr[pos], cur);
}

static void maybe_insert_score(Entry arr[TOPK], const Entry *cur, int by_h_over_n) {
    double score = by_h_over_n ? cur->h_over_n_score : cur->d_score;
    int pos = -1;
    for (int i = 0; i < TOPK; i++) {
        if (!arr[i].line) {
            pos = i;
            break;
        }
        double old = by_h_over_n ? arr[i].h_over_n_score : arr[i].d_score;
        if (score > old) {
            pos = i;
            break;
        }
    }
    if (pos < 0) return;
    free_entry(&arr[TOPK - 1]);
    for (int i = TOPK - 1; i > pos; i--) arr[i] = arr[i - 1];
    memset(&arr[pos], 0, sizeof(arr[pos]));
    copy_entry(&arr[pos], cur);
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

static void print_table(const char *name, Entry arr[TOPK]) {
    printf("# %s\n", name);
    printf("rank\tn\td\tH\td_score\tlog10_H_over_n\tline\n");
    for (int i = 0; i < TOPK && arr[i].line; i++) {
        printf("%d\t%llu\t%s\t%s\t%.12g\t%.12g\t%s\n",
               i + 1, arr[i].n, arr[i].d, arr[i].h,
               arr[i].d_score, arr[i].h_over_n_score, arr[i].line);
    }
}

int main(void) {
    char *line = NULL;
    size_t cap = 0;
    unsigned long long count = 0;
    while (getline(&line, &cap, stdin) != -1) {
        size_t l = strlen(line);
        while (l && (line[l - 1] == '\n' || line[l - 1] == '\r')) line[--l] = '\0';
        if (!l) continue;
        unsigned long long n = strtoull(line, NULL, 10);
        NumRef nums[4];
        if (!parse_coeffs(line, nums)) {
            fprintf(stderr, "Could not parse line: %s\n", line);
            continue;
        }
        char *d = abs_sum(nums[2], nums[3]);
        NumRef hnum = nums[0];
        for (int i = 1; i < 4; i++) {
            if (cmp_numref_abs(nums[i], hnum) > 0) hnum = nums[i];
        }
        char *h = numref_abs_string(hnum);
        double nd = n > 1 ? (double)n : 2.0;
        double denom = sqrt(log(nd) * log(log(nd)));
        double dscore = denom > 0 ? decimal_to_double_limited(d) / denom : 0.0;
        double h_over_n = decimal_log10(h) - log10(nd);
        Entry cur = {
            .n = n,
            .line = line,
            .d = d,
            .h = h,
            .d_score = dscore,
            .h_over_n_score = h_over_n,
        };
        maybe_insert_decimal(top_d, &cur, 0);
        maybe_insert_decimal(top_h, &cur, 1);
        maybe_insert_score(top_d_score, &cur, 0);
        maybe_insert_score(top_h_over_n, &cur, 1);
        free(d);
        free(h);
        count++;
        if (count % 10000000ULL == 0) {
            fprintf(stderr, "processed %llu lines; current n=%llu\n", count, n);
        }
    }
    free(line);
    fprintf(stderr, "processed %llu lines total\n", count);
    print_table("largest_d", top_d);
    print_table("largest_H", top_h);
    print_table("largest_d_over_sqrt_log", top_d_score);
    print_table("largest_log10_H_over_n", top_h_over_n);
    return 0;
}

#include <stdio.h>
#include <math.h>
#include <stdlib.h>

#define LIMIT 7
#define NUMS_SIZE 2
#define OPS_SIZE 5

typedef double (*op_func)(double, double);

double add(double a, double b) { return a + b; }
double sub(double a, double b) { return a - b; }
double mul(double a, double b) { return a * b; }
double truediv(double a, double b) { return a / b; }
double power(double a, double b) { return pow(a, b); }

typedef struct {
    void *expr;
    int type;  // 0: double, 1: tuple
} Expr;

typedef struct {
    op_func op;
    Expr left;
    Expr right;
} Tuple;

typedef struct {
    Expr *expr;
    int size;
    int capacity;
} ExprList;

ExprList *create_expr_list(int capacity) {
    ExprList *list = (ExprList *)malloc(sizeof(ExprList));
    list->expr = (Expr *)malloc(sizeof(Expr) * capacity);
    list->size = 0;
    list->capacity = capacity;
    return list;
}

void append_expr_list(ExprList *list, Expr expr) {
    if (list->size == list->capacity) {
        list->capacity *= 2;
        list->expr = (Expr *)realloc(list->expr, sizeof(Expr) * list->capacity);
    }
    list->expr[list->size++] = expr;
}

void free_expr_list(ExprList *list) {
    for (int i = 0; i < list->size; i++) {
        if (list->expr[i].type == 1) {
            free(((Tuple *)list->expr[i].expr)->left.expr);
            free(((Tuple *)list->expr[i].expr)->right.expr);
            free(list->expr[i].expr);
        }
    }
    free(list->expr);
    free(list);
}

Expr create_double_expr(double value) {
    Expr expr;
    expr.expr = malloc(sizeof(double));
    *(double *)expr.expr = value;
    expr.type = 0;
    return expr;
}

Expr create_tuple_expr(op_func op, Expr left, Expr right) {
    Tuple *tuple = (Tuple *)malloc(sizeof(Tuple));
    tuple->op = op;
    tuple->left = left;
    tuple->right = right;
    Expr expr;
    expr.expr = tuple;
    expr.type = 1;
    return expr;
}

ExprList *expr_iter(op_func *ops, double *nums, int limit) {
    ExprList *list = create_expr_list(100);

    if (limit == 0)
        return list;

    for (int i = 0; i < NUMS_SIZE; i++) {
        append_expr_list(list, create_double_expr(nums[i]));
    }

    for (int i = 0; i < OPS_SIZE; i++) {
        ExprList *left_list = expr_iter(ops, nums, limit - 1);
        for (int j = 0; j < left_list->size; j++) {
            Expr left = left_list->expr[j];
            ExprList *right_list = expr_iter(ops, nums, limit - (left.type == 1 ? 1 : 0));
            for (int k = 0; k < right_list->size; k++) {
                Expr right = right_list->expr[k];
                append_expr_list(list, create_tuple_expr(ops[i], left, right));
            }
            free_expr_list(right_list);
        }
        free_expr_list(left_list);
    }

    return list;
}

double expr_eval(Expr expr) {
    if (expr.type == 0) {
        return *(double *)expr.expr;
    } else {
        Tuple *tuple = (Tuple *)expr.expr;
        return tuple->op(expr_eval(tuple->left), expr_eval(tuple->right));
    }
}

void expr_repr(Expr expr, char *buffer) {
    if (expr.type == 0) {
        double value = *(double *)expr.expr;
        if (value == M_PI) {
            sprintf(buffer, "pi");
        } else if (value == M_E) {
            sprintf(buffer, "e");
        }
    } else {
        Tuple *tuple = (Tuple *)expr.expr;
        char left_buffer[256], right_buffer[256];
        expr_repr(tuple->left, left_buffer);
        expr_repr(tuple->right, right_buffer);
        char op;
        if (tuple->op == add) op = '+';
        else if (tuple->op == sub) op = '-';
        else if (tuple->op == mul) op = '*';
        else if (tuple->op == truediv) op = '/';
        else if (tuple->op == power) op = '^';
        sprintf(buffer, "(%s %c %s)", left_buffer, op, right_buffer);
    }
}

int main() {
    op_func ops[OPS_SIZE] = {add, sub, mul, truediv, power};
    double nums[NUMS_SIZE] = {M_E, M_PI};

    ExprList *list = expr_iter(ops, nums, LIMIT);
    for (int i = 0; i < list->size; i++) {
        Expr expr = list->expr[i];

        double v = expr_eval(expr);
        if (floor(v) == 114514) {
            char buffer[256];
            expr_repr(expr, buffer);
            printf("%s = %f\n", buffer, v);
        }

    }

    free_expr_list(list);
    return 0;
}

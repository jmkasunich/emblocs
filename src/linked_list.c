#include "linked_list.h"

#include "printing.h"

int ll_insert(void **root, void *node, ll_funct_cmp_nodes_t funct)
{
    void **p = root;
    void **n = node;
    int retval;
print_string("ll_insert()\n");
    do {
        if ( *p == NULL ) {
            // reached end of list, insert here
            *n = *p;
            *p = node;
            return 0;
        }
        retval = funct(*p, node);
        if ( retval > 0 ) {
            // found the right place, insert
            *n = *p;
            *p = node;
            return 0;
        } else if ( retval == 0 ) {
            // duplicate
            return -1;
        } else {
            // not there yet, go to next
            p = *p;
        }
    } while (1);
}

void *ll_find(void **root, void *key, ll_funct_cmp_node_key_t funct)
{
    void **p = root;
print_string("ll_find()\n");

    while ( *p != NULL ) {
        if ( funct(*p, key) == 0 ) {
            // match
            return *p;
        }
        p = *p;
    }
    // not found
    return NULL;
}

void *ll_delete(void **root, void *key, ll_funct_cmp_node_key_t funct)
{
    void **p = root;
    void **n;
print_string("ll_delete()\n");

    while ( *p != NULL ) {
        if ( funct(*p, key) == 0 ) {
            // match, point at node
            n = *p;
            // link arounnd it
            *p = *n;
            *n = NULL;
            return n;
        }
        p = *p;
    }
    // not found
    return NULL;
}

int ll_traverse(void **root, ll_funct_process_node_t funct)
{
    void **p = root;
    int count = 0;
print_string("ll_traverse()\n");

    while ( *p != NULL ) {
        if ( funct != NULL ) funct(*p);
        p = *p;
        count++;
    }
    return count;
}

void *ll_next(void *node)
{
    void **p = node;

    return *p;
}


/* test and demo code, will probably be deleted or moved to another file */

#include <string.h>
#include "printing.h"

typedef struct foo_s {
    struct foo_s *next;
    int data1;
    char *data2;
} foo_t;

int foo_cmp_node_key(void *node, void *key)
{
    foo_t *np = node;
    char *kp = key;
    return strcmp(np->data2, kp);
}

int foo_cmp_nodes(void *node1, void *node2)
{
    foo_t *np1 = node1;
    foo_t *np2 = node2;
    return strcmp(np1->data2, np2->data2);
}

void foo_print_node(void *node)
{
    foo_t *np = node;
    printf("foo node at %p; next = %p, data1 = %d, data2 = %s\n", np, np->next, np->data1, np->data2 );
}

int foo_insert(foo_t **root, foo_t *node)
{
    return ll_insert((void **)root, (void *)node, foo_cmp_nodes);
}

int foo_print_list(foo_t **root)
{
    return ll_traverse((void **)root, foo_print_node);
}

void *foo_find(foo_t **root, char *key)
{
    return ll_find((void **)root, (void *)key, foo_cmp_node_key);
}

void *foo_delete(foo_t **root, char *key)
{
    return ll_delete((void **)root, (void *)key, foo_cmp_node_key);
}


/*
typedef struct bar_s {
    struct bar_s *next;
    char *keystring;
} bar_t;

int bar_cmp_node_key(void *node, void *key)
{
    bar_t *np = node;
    char *kp = key;

    return strcmp(np->keystring, kp);
}

int bar_cmp_nodes(void *node1, void *node2)
{
    bar_t *np1 = node1;
    bar_t *np2 = node2;

    return strcmp(np1->keystring, np2->keystring);
}

void bar_print_node(void *node)
{
    bar_t *np = node;

    printf("bar node at %p; next = %p, keystring = %s\n", np, np->next, np->keystring );
}

*/


int linked_list_test(void)
{
    foo_t *foo_root = NULL;
 
    foo_t foo_node1 = {
        NULL, 27, "foo_node_1"
    };
    
    foo_t foo_node2 = {
        NULL, 42, "foo_node_2"
    };

    foo_t foo_node3 = {
        NULL, 33, "foo_node_3"
    };

    foo_t foo_node4 = {
        NULL, 13, "foo_node_4"
    };



    printf("%d entries\n", foo_print_list(&foo_root));
    foo_insert(&foo_root, &foo_node3);
    foo_insert(&foo_root, &foo_node2);
    foo_insert(&foo_root, &foo_node1);
    foo_insert(&foo_root, &foo_node2);
    printf("%d entries\n", foo_print_list(&foo_root));
    foo_delete(&foo_root, "foo_node_2");
    printf("%d entries\n", foo_print_list(&foo_root));
    foo_insert(&foo_root, &foo_node4);
    printf("%d entries\n", foo_print_list(&foo_root));
    foo_delete(&foo_root, "foo_node_1");
    printf("%d entries\n", foo_print_list(&foo_root));

    
    return 0;
}
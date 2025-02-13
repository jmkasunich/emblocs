
/****************************************************************
 * Generic sorted linked List 
 * 
 *  - The "next" link is the first item in node and is a void pointer
 *  - Other data follows the next link and can be anything
 *  - The caller supplies functions as follows:
 *       to compare two nodes (for insert)
 *       to compare a node and a key (for find or delete) 
 *       to process a node (for traverse)
 * 
 */

#ifndef LINKED_LIST_H
#define LINKED_LIST_H

#include <stddef.h>

/**************************************************************
 * prototype for caller-supplied function that defines the
 * list sort order.  It must return
 *   zero if 'node1' and 'node2' have the same key
 *   positive if 'node1' is greater than (comes after) 'node2'
 *   negative if 'node1' is less than (comes before) 'node2'
 */
typedef int (*ll_funct_cmp_nodes_t)(void *node1, void *node2);

/**************************************************************
 * prototype for caller-supplied function that compares a key
 * to a node.  It must return
 *   zero if 'node' matches 'key'
 *   non-zero if 'node' does not match 'key'
 *   (non-zero result can be positive or negative)
 */
typedef int (*ll_funct_cmp_node_key_t)(void *node, void *key);

/**************************************************************
 * prototype for caller-supplied function that can do anything
 * required with a node; for example it might print the contents
 */
typedef void (*ll_funct_process_node_t)(void *node);

/**************************************************************
 * inserts 'node' into the list based at 'root', using 'funct'
 * to define the sort order.  Returns zero on success, or -1
 * if a node with the same key is already in the list
 */
int ll_insert(void **root, void *node, ll_funct_cmp_nodes_t funct);

/**************************************************************
 * finds a node that matches 'key' in the list based at
 * 'root', using 'funct' to detect the match.  Returns a
 * pointer to the matching node on success, or NULL if a match
 * is not fount
 */
void * ll_find(void **root, void *key, ll_funct_cmp_node_key_t funct);

/**************************************************************
 * deletes a node that matches 'key' from the list based at
 * 'root', using 'funct' to detect the match.  Returns a
 * pointer to the deleted node on success, or NULL if a match
 * is not fount
 */
void * ll_delete(void **root, void *key, ll_funct_cmp_node_key_t funct);

/**************************************************************
 * traverses the list based at 'root', calling 'funct' for each
 * node in the list.  Returns the number of nodes in the list.
 * 'funct' can be NULL, in which case it simply returns the
 * number of nodes.
 */
int ll_traverse(void **root, ll_funct_process_node_t funct);

/**************************************************************
 * returns a pointer to the node that follows 'node', or NULL
 * if 'node' is at the end of the list.  Can be used to manually
 * traverse a list, but see 'll_traverse' above.
 */
void * ll_next(void *node);


int linked_list_test(void);

#endif // LINKED_LIST_H


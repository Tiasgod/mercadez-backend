package com.mercadez.controller;

import com.mercadez.dto.*;
import com.mercadez.service.ProdutoService;
import jakarta.validation.Valid;
import org.springframework.http.*;
import org.springframework.security.core.Authentication;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequestMapping("/produtos")
public class ProdutoController {

    private final ProdutoService service;

    public ProdutoController(ProdutoService service) { this.service = service; }

    /**
     * GET /produtos
     * Lista todos os produtos ativos — público.
     * Aceita ?afiliado=<id> para filtrar por loja.
     */
    @GetMapping
    public ResponseEntity<List<ProdutoResponse>> listar(
            @RequestParam(required = false) Long afiliado) {

        if (afiliado != null) {
            return ResponseEntity.ok(service.listarPorAfiliado(afiliado));
        }
        return ResponseEntity.ok(service.listarTodos());
    }

    /**
     * GET /produtos/buscar?q=arroz
     * Busca por nome/tag — usado pelo busca.js
     */
    @GetMapping("/buscar")
    public ResponseEntity<List<ProdutoResponse>> buscar(@RequestParam String q) {
        return ResponseEntity.ok(service.buscar(q));
    }

    /**
     * GET /produtos/comparar?nome=leite
     * Comparação de preços entre afiliados
     */
    @GetMapping("/comparar")
    public ResponseEntity<List<ProdutoResponse>> comparar(@RequestParam String nome) {
        return ResponseEntity.ok(service.comparar(nome));
    }

    /**
     * POST /produtos
     * Cadastra produto — apenas afiliado autenticado.
     * O afiliadoId é extraído do JWT (não do body).
     */
    @PostMapping
    public ResponseEntity<ProdutoResponse> cadastrar(
            @Valid @RequestBody CadastroProdutoRequest req,
            Authentication auth) {

        Long afiliadoId = (Long) auth.getDetails();
        return ResponseEntity.status(HttpStatus.CREATED).body(service.cadastrar(req, afiliadoId));
    }

    /**
     * PUT /produtos/{id}
     * Atualiza produto — verifica dono pelo JWT.
     */
    @PutMapping("/{id}")
    public ResponseEntity<ProdutoResponse> atualizar(
            @PathVariable Long id,
            @Valid @RequestBody CadastroProdutoRequest req,
            Authentication auth) {

        Long afiliadoId = (Long) auth.getDetails();
        return ResponseEntity.ok(service.atualizar(id, req, afiliadoId));
    }

    /**
     * DELETE /produtos/{id}
     * Soft-delete — verifica dono pelo JWT.
     */
    @DeleteMapping("/{id}")
    public ResponseEntity<Void> deletar(@PathVariable Long id, Authentication auth) {
        Long afiliadoId = (Long) auth.getDetails();
        service.deletar(id, afiliadoId);
        return ResponseEntity.noContent().build();
    }
}

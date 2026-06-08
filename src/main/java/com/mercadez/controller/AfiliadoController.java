package com.mercadez.controller;

import com.mercadez.dto.*;
import com.mercadez.service.AfiliadoService;
import jakarta.validation.Valid;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.Authentication;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/afiliados")
public class AfiliadoController {

    private final AfiliadoService service;

    public AfiliadoController(AfiliadoService service) { this.service = service; }

    /** POST /afiliados — cadastro de novo afiliado (lojista) */
    @PostMapping
    public ResponseEntity<AfiliadoResponse> cadastrar(@Valid @RequestBody CadastroAfiliadoRequest req) {
        return ResponseEntity.status(HttpStatus.CREATED).body(service.cadastrar(req));
    }

    /** POST /afiliados/login */
    @PostMapping("/login")
    public ResponseEntity<LoginResponse> login(@Valid @RequestBody LoginRequest req) {
        return ResponseEntity.ok(service.login(req));
    }

    /** GET /afiliados/me — dados do afiliado logado */
    @GetMapping("/me")
    public ResponseEntity<AfiliadoResponse> me(Authentication auth) {
        Long id = (Long) auth.getDetails();
        return ResponseEntity.ok(service.buscarPorId(id));
    }
}

package com.mercadez.controller;

import com.mercadez.dto.*;
import com.mercadez.service.UsuarioService;
import jakarta.validation.Valid;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.Authentication;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/usuarios")
public class UsuarioController {

    private final UsuarioService service;

    public UsuarioController(UsuarioService service) { this.service = service; }

    /** POST /usuarios/cadastro — rota pública */
    @PostMapping("/cadastro")
    public ResponseEntity<UsuarioResponse> cadastrar(@Valid @RequestBody CadastroUsuarioRequest req) {
        return ResponseEntity.status(HttpStatus.CREATED).body(service.cadastrar(req));
    }

    /** POST /usuarios/login — rota pública */
    @PostMapping("/login")
    public ResponseEntity<LoginResponse> login(@Valid @RequestBody LoginRequest req) {
        return ResponseEntity.ok(service.login(req));
    }

    /** GET /usuarios/me — requer autenticação */
    @GetMapping("/me")
    public ResponseEntity<UsuarioResponse> me(Authentication auth) {
        Long id = (Long) auth.getDetails();
        return ResponseEntity.ok(service.buscarPorId(id));
    }
}
